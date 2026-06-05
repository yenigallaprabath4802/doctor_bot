/**
 * RTVI Client Wrapper for AirOwl
 * ======================================
 * Simplified WebRTC + RTVI connection handler
 */

class RTVIClient {
    constructor(options) {
        this.baseUrl = options.baseUrl || 'http://localhost:7860';
        this.config = options.config || {};
        this.callbacks = {
            onConnected: options.onConnected || (() => { }),
            onDisconnected: options.onDisconnected || (() => { }),
            onTranscript: options.onTranscript || (() => { }),
            onBotResponse: options.onBotResponse || (() => { }),
            onMetrics: options.onMetrics || (() => { }),
            onPipelineState: options.onPipelineState || (() => { })
        };

        this.peerConnection = null;
        this.dataChannel = null;
        this.localStream = null;
    }

    async connect() {
        try {
            // Get local audio stream
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // Create peer connection
            this.peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' }
                ]
            });

            // Add local audio track
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });

            // Handle incoming audio (bot's voice)
            this.peerConnection.ontrack = (event) => {
                const audioEl = document.createElement('audio');
                audioEl.srcObject = event.streams[0];
                audioEl.autoplay = true;
                document.body.appendChild(audioEl);
            };

            // Create data channel for messages
            this.dataChannel = this.peerConnection.createDataChannel('rtvi', {
                ordered: true
            });

            this.dataChannel.onopen = () => {
                console.log('Data channel opened');
                // Send initial config
                this.sendConfig(this.config);
            };

            this.dataChannel.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };

            // ICE candidate handling
            this.peerConnection.onicecandidate = async (event) => {
                if (event.candidate) {
                    await this.sendIceCandidate(event.candidate);
                }
            };

            // Connection state
            this.peerConnection.onconnectionstatechange = () => {
                console.log('Connection state:', this.peerConnection.connectionState);
                if (this.peerConnection.connectionState === 'connected') {
                    this.callbacks.onConnected();
                } else if (this.peerConnection.connectionState === 'disconnected' ||
                    this.peerConnection.connectionState === 'failed') {
                    this.callbacks.onDisconnected();
                }
            };

            // Create and send offer
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);

            // Send offer to backend and get answer
            const response = await fetch(`${this.baseUrl}/api/rtvi/connect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sdp: offer.sdp,
                    type: offer.type,
                    config: this.config
                })
            });

            if (!response.ok) {
                throw new Error('Failed to connect to RTVI backend');
            }

            const answer = await response.json();
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription({
                type: answer.type,
                sdp: answer.sdp
            }));

            console.log('RTVI connection established');

        } catch (error) {
            console.error('RTVI connection error:', error);
            throw error;
        }
    }

    async sendIceCandidate(candidate) {
        try {
            await fetch(`${this.baseUrl}/api/rtvi/ice`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidate })
            });
        } catch (error) {
            console.error('Failed to send ICE candidate:', error);
        }
    }

    handleMessage(message) {
        switch (message.type) {
            case 'transcript':
                this.callbacks.onTranscript(message.text, message.isFinal);
                break;
            case 'bot-response':
                this.callbacks.onBotResponse(message.text);
                break;
            case 'metrics':
                this.callbacks.onMetrics(message.data);
                break;
            case 'pipeline-state':
                this.callbacks.onPipelineState(message.data);
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    sendConfig(config) {
        if (this.dataChannel && this.dataChannel.readyState === 'open') {
            this.dataChannel.send(JSON.stringify({
                type: 'config-update',
                config: config
            }));
        }
    }

    updateConfig(config) {
        this.config = { ...this.config, ...config };
        this.sendConfig(this.config);
    }

    async disconnect() {
        if (this.dataChannel) {
            this.dataChannel.close();
        }
        if (this.peerConnection) {
            this.peerConnection.close();
        }
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }

        this.callbacks.onDisconnected();
    }
}

// Export for use
window.RTVIClient = RTVIClient;
