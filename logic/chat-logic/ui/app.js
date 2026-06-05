/**
 * AI Teaching Assistant — Frontend Controller
 * AI PC for Educators Course
 */

class TeachingAssistantApp {
    constructor() {
        this.peerConnection = null;
        this.localStream = null;
        this.remoteAudio = null;
        this.dataChannel = null;
        this.isConnected = false;

        this._currentBotBubble = null;

        this.config = {
            mode: 'faq',
            teachingStyle: 'supportive',
            customInstructions: '',
            courseName: '',
            llmParams: { temperature: 0.3, max_tokens: 150 },
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadConfig();
        console.log('Spark initialized');
    }

    bindEvents() {
        // Tab Navigation
        document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.currentTarget));
        });

        // Connection
        document.getElementById('startBtn')?.addEventListener('click', () => this.connect());
        document.getElementById('stopBtn')?.addEventListener('click', () => this.disconnect());

        // Config Deploy
        document.getElementById('deployConfigBtn')?.addEventListener('click', () => this.deployConfig());

        // Mode Buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.setMode(e.currentTarget.dataset.mode);
            });
        });

        // Style Buttons
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.setStyle(e.currentTarget.dataset.style);
            });
        });

        // Activity toggle
        document.getElementById('activityToggle')?.addEventListener('click', () => {
            const bar = document.getElementById('activityBar');
            const toggle = document.getElementById('activityToggle');
            if (bar && toggle) {
                const visible = bar.style.display !== 'none';
                bar.style.display = visible ? 'none' : 'block';
                toggle.classList.toggle('active', !visible);
            }
        });

        // Reload Materials
        document.getElementById('reloadMaterialsBtn')?.addEventListener('click', () => this.reloadMaterials());

        // Sliders
        document.getElementById('llmTokens')?.addEventListener('input', (e) => {
            document.getElementById('tokensDisplay').textContent = e.target.value;
            this.config.llmParams.max_tokens = parseInt(e.target.value);
        });

        document.getElementById('llmTemp')?.addEventListener('input', (e) => {
            document.getElementById('tempDisplay').textContent = e.target.value;
            this.config.llmParams.temperature = parseFloat(e.target.value);
        });
    }

    switchTab(btn) {
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const tabId = btn.dataset.tab;
        document.querySelectorAll('.view-panel').forEach(view => view.classList.remove('active'));

        if (tabId === 'dashboard') {
            document.getElementById('view-dashboard').classList.add('active');
        } else {
            document.getElementById('view-config').classList.add('active');
        }
    }

    // ==========================================
    // ORB ANIMATION
    // ==========================================

    setOrbSpeaking(speaking) {
        const container = document.getElementById('orbContainer');
        const status = document.getElementById('orbStatus');

        if (speaking) {
            container?.classList.add('speaking');
            if (status) status.textContent = 'Speaking...';
        } else {
            container?.classList.remove('speaking');
            if (status) status.textContent = 'Ready';
        }
    }

    setOrbListening(listening) {
        const status = document.getElementById('orbStatus');
        if (listening && status) {
            status.textContent = 'Listening...';
        }
    }

    // ==========================================
    // MODE & STYLE
    // ==========================================

    async setMode(mode) {
        this.config.mode = mode;

        // Update mode badge
        const modeLabels = { faq: 'Course FAQ', assignment: 'Assignment Help', lecture: 'Lecture Q&A' };
        const badge = document.getElementById('modeBadge');
        if (badge) badge.textContent = modeLabels[mode] || mode;

        // Send to backend
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode }),
        });

        this.addMessage('system', `Switched to ${modeLabels[mode] || mode} mode`);
        this.updateMaterialsUI();
    }

    async setStyle(style) {
        this.config.teachingStyle = style;

        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ teachingStyle: style }),
        });

        this.addMessage('system', `Teaching style: ${style}`);
    }

    // ==========================================
    // MATERIALS
    // ==========================================

    async reloadMaterials() {
        const btn = document.getElementById('reloadMaterialsBtn');
        if (btn) {
            btn.textContent = 'Reloading...';
            btn.disabled = true;
        }

        try {
            const res = await fetch('/api/materials/reload', { method: 'POST' });
            const data = await res.json();

            if (data.materials) {
                this._materials = data.materials;
                this.updateMaterialsUI();
            }

            this.addMessage('system', 'Course materials reloaded');
        } catch (e) {
            console.error('Failed to reload materials', e);
        } finally {
            if (btn) {
                btn.textContent = 'Reload Materials';
                btn.disabled = false;
            }
        }
    }

    updateMaterialsUI() {
        const container = document.getElementById('materialsList');
        if (!container || !this._materials) return;

        const files = this._materials[this.config.mode] || [];

        if (files.length === 0) {
            container.innerHTML = '<span class="materials-empty">No files loaded for this mode. Add documents to course_materials/</span>';
            return;
        }

        container.innerHTML = files.map(f =>
            `<div class="file-item"><svg class="file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>${f}</div>`
        ).join('');
    }

    // ==========================================
    // CONFIGURATION
    // ==========================================

    async loadConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();

            if (data.mode) {
                this.config.mode = data.mode;
                document.querySelectorAll('.mode-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.mode === data.mode);
                });
                const modeLabels = { faq: 'Course FAQ', assignment: 'Assignment Help', lecture: 'Lecture Q&A' };
                const badge = document.getElementById('modeBadge');
                if (badge) badge.textContent = modeLabels[data.mode] || data.mode;
            }

            if (data.teachingStyle) {
                this.config.teachingStyle = data.teachingStyle;
                document.querySelectorAll('.style-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.style === data.teachingStyle);
                });
            }

            if (data.customInstructions) {
                document.getElementById('customInstructions').value = data.customInstructions;
            }

            if (data.courseName) {
                this.config.courseName = data.courseName;
                document.getElementById('courseName').value = data.courseName;
            }

            if (data.materials) {
                this._materials = data.materials;
                this.updateMaterialsUI();
            }

        } catch (e) {
            console.error('Failed to load config', e);
        }
    }

    async deployConfig() {
        const payload = {
            customInstructions: document.getElementById('customInstructions')?.value || '',
            courseName: document.getElementById('courseName')?.value || '',
            llmParams: this.config.llmParams,
        };

        try {
            const btn = document.getElementById('deployConfigBtn');
            const originalText = btn?.textContent;
            if (btn) btn.textContent = 'Saving...';

            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (btn) {
                btn.textContent = 'Saved!';
                setTimeout(() => btn.textContent = originalText, 2000);
            }

            this.addMessage('system', 'Settings updated');

        } catch (e) {
            console.error('Deploy failed', e);
        }
    }

    // ==========================================
    // WEBRTC & RTVI
    // ==========================================

    async connect() {
        try {
            this.updateStatus('connecting');
            this.addMessage('system', 'Starting session...');

            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true },
            });

            this.peerConnection = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
            });

            this.dataChannel = this.peerConnection.createDataChannel('rtvi', { ordered: true });
            this.setupDataChannel(this.dataChannel);

            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });

            this.peerConnection.ontrack = (event) => {
                if (event.track.kind === 'audio') {
                    this.remoteAudio = new Audio();
                    this.remoteAudio.srcObject = event.streams[0];
                    this.remoteAudio.play().catch(e => console.log('Autoplay blocked', e));
                }
            };

            this.peerConnection.onconnectionstatechange = () => {
                const state = this.peerConnection.connectionState;
                console.log('Connection:', state);
                if (state === 'connected') this.onConnected();
                else if (['disconnected', 'closed', 'failed'].includes(state)) this.onDisconnected();
            };

            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);

            // Wait for ICE gathering
            if (this.peerConnection.iceGatheringState !== 'complete') {
                await new Promise(resolve => {
                    const checkState = () => {
                        if (this.peerConnection.iceGatheringState === 'complete') {
                            this.peerConnection.removeEventListener('icegatheringstatechange', checkState);
                            resolve();
                        }
                    };
                    this.peerConnection.addEventListener('icegatheringstatechange', checkState);
                });
            }

            const response = await fetch('/api/offer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sdp: this.peerConnection.localDescription.sdp,
                    type: this.peerConnection.localDescription.type,
                }),
            });

            const answer = await response.json();
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(answer));

            document.getElementById('startBtn').style.display = 'none';
            document.getElementById('stopBtn').style.display = 'block';

        } catch (e) {
            console.error('Connection failed', e);
            this.updateStatus('disconnected');
            this.addMessage('system', 'Connection failed: ' + e.message);
        }
    }

    setupDataChannel(channel) {
        channel.onopen = () => {
            console.log('Data channel open, state:', channel.readyState);
            this.pingInterval = setInterval(() => {
                if (channel.readyState === 'open') channel.send('ping:' + Date.now());
            }, 1000);
        };

        channel.onclose = () => console.log('Data channel closed');
        channel.onerror = (e) => console.error('Data channel error:', e);

        channel.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                if (msg.label === 'rtvi-ai') {
                    this.handleRTVI(msg);
                }
            } catch (err) {
                // ping responses or non-JSON
            }
        };
    }

    handleRTVI(msg) {
        const { type, data } = msg;

        switch (type) {
            case 'user-started-speaking':
                this.setOrbListening(true);
                break;

            case 'user-transcription':
                if (data.final) {
                    this.addMessage('user', data.text);
                }
                break;

            case 'bot-tts-started':
                this.setOrbSpeaking(true);
                this._currentBotBubble = null;
                break;

            case 'bot-tts-text':
                this.appendBotMessage(data.text);
                break;

            case 'bot-stopped-speaking':
                this.setOrbSpeaking(false);
                this._finalizeBotBubble();
                break;
        }
    }

    appendBotMessage(text) {
        if (!this._currentBotBubble) {
            const div = document.createElement('div');
            div.className = 'bubble assistant';
            div.innerHTML = `<span class="bubble-label">Spark</span><span class="bubble-text"></span>`;
            const log = document.getElementById('chatContainer');
            log.appendChild(div);
            this._currentBotBubble = div;
        }
        const span = this._currentBotBubble.querySelector('.bubble-text');
        if (span) {
            // Ensure spaces after sentence-ending punctuation
            const spaced = text.replace(/([.!?])([A-Z])/g, '$1 $2');
            const current = span.textContent;
            const trimmed = spaced.trim();
            if (current && trimmed) {
                span.textContent = current.trimEnd() + ' ' + trimmed;
            } else {
                span.textContent = current + trimmed;
            }
        }
        const log = document.getElementById('chatContainer');
        log.scrollTop = log.scrollHeight;
    }

    _finalizeBotBubble() {
        if (this._currentBotBubble) {
            const ts = document.createElement('span');
            ts.className = 'timestamp';
            ts.textContent = this._formatTime();
            this._currentBotBubble.appendChild(ts);
            this._currentBotBubble = null;
        }
    }

    disconnect() {
        if (this.peerConnection) this.peerConnection.close();
        if (this.localStream) this.localStream.getTracks().forEach(t => t.stop());
        if (this.pingInterval) clearInterval(this.pingInterval);

        this.updateStatus('disconnected');
        document.getElementById('startBtn').style.display = 'block';
        document.getElementById('stopBtn').style.display = 'none';
        this.addMessage('system', 'Session ended');
        this.setOrbSpeaking(false);
    }

    onConnected() {
        this.isConnected = true;
        this.updateStatus('connected');
        this.addMessage('system', 'Session active. Start talking!');
    }

    onDisconnected() {
        this.isConnected = false;
        this.updateStatus('disconnected');
    }

    updateStatus(status) {
        const el = document.getElementById('connectionStatus');
        el.className = `connection-status ${status}`;
        const statusText = {
            'connected': 'ACTIVE',
            'connecting': 'CONNECTING...',
            'disconnected': 'STANDBY',
        };
        el.querySelector('.status-text').textContent = statusText[status] || 'STANDBY';
    }

    addMessage(role, text) {
        if (role === 'system') {
            this.addActivity(text);
            return;
        }

        const div = document.createElement('div');
        div.className = `bubble ${role}`;
        const time = this._formatTime();

        if (role === 'assistant') {
            div.innerHTML = `<span class="bubble-label">Spark</span><span class="bubble-text">${text}</span><span class="timestamp">${time}</span>`;
        } else if (role === 'user') {
            div.innerHTML = `<span class="bubble-label" style="text-align:right">You</span><span class="bubble-text">${text}</span><span class="timestamp">${time}</span>`;
        }

        const log = document.getElementById('chatContainer');
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }

    addActivity(text) {
        const log = document.getElementById('activityLog');
        if (!log) return;
        const item = document.createElement('div');
        item.className = 'activity-item';
        item.innerHTML = `<span class="activity-time">${this._formatTime()}</span>${text}`;
        log.appendChild(item);
        log.scrollTop = log.scrollHeight;
    }

    _formatTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new TeachingAssistantApp();
});
