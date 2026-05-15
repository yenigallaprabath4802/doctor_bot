// Voice input handler
const voiceBtn = document.getElementById('voice-btn');
const chatMessage = document.getElementById('chat_message');
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (voiceBtn) {
    voiceBtn.addEventListener('click', function() {
        if (!SpeechRecognition) {
            alert('Speech recognition is not supported in this browser. Use Chrome, Edge, or Safari with microphone access enabled.');
            return;
        }

        if (!chatMessage) {
            alert('Message input not found.');
            return;
        }

        const recognition = new SpeechRecognition();
        
        // Detect language from user preference or browser default
        let language = 'en-US';
        const userLanguage = document.documentElement.lang || navigator.language || 'en-US';
        if (userLanguage.includes('hi') || userLanguage.includes('hin')) {
            language = 'hi-IN';
        } else if (userLanguage.includes('te') || userLanguage.includes('tel')) {
            language = 'te-IN';
        } else {
            language = userLanguage.startsWith('en') ? 'en-US' : userLanguage;
        }
        
        recognition.lang = language;
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        voiceBtn.textContent = '🎤 Listening...';
        voiceBtn.disabled = true;

        recognition.onstart = function() {
            console.log('Speech recognition started');
        };

        recognition.onresult = function(event) {
            console.log('SpeechRecognition onresult:', event);

            let transcript = '';
            
            // Collect all results
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result && result[0] && result[0].transcript) {
                    transcript += result[0].transcript;
                }
            }

            transcript = (transcript || '').trim();
            console.log('Final transcript:', transcript);
            
            if (transcript) {
                chatMessage.value = transcript;
                chatMessage.focus();
                
                // Auto-submit the form after a short delay to allow DOM update
                setTimeout(() => {
                    const form = chatMessage.closest('form');
                    if (form) {
                        console.log('Auto-submitting form with transcript:', transcript);
                        form.submit();
                    }
                }, 100);
            } else {
                alert('No speech detected. Please try again.');
                voiceBtn.textContent = '🎤';
                voiceBtn.disabled = false;
            }
        };

        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            let errorMsg = event.error;
            
            // User-friendly error messages
            if (event.error === 'no-speech') {
                errorMsg = 'No speech detected. Please speak clearly into your microphone.';
            } else if (event.error === 'network') {
                errorMsg = 'Network error. Please check your internet connection.';
            } else if (event.error === 'not-allowed') {
                errorMsg = 'Microphone access denied. Please grant microphone permission in your browser settings.';
            }
            
            alert('Speech recognition error: ' + errorMsg);
            voiceBtn.textContent = '🎤';
            voiceBtn.disabled = false;
        };

        recognition.onend = function() {
            console.log('Speech recognition ended');
            voiceBtn.textContent = '🎤';
            voiceBtn.disabled = false;
        };

        recognition.start();
    });
}

const speakBtn = document.getElementById('speak-btn');

if (speakBtn) {
    speakBtn.addEventListener('click', function() {
        const botMessages = document.querySelectorAll('.chat-row.bot .chat-text');
        const lastBotMessage = botMessages[botMessages.length - 1];
        const text = lastBotMessage ? lastBotMessage.textContent.trim() : '';
        if (!text) {
            alert('No bot message to speak.');
            return;
        }

        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = navigator.language || 'en-US';
            utterance.rate = 1;
            utterance.pitch = 1;
            window.speechSynthesis.speak(utterance);
            return;
        }

        const formData = new FormData();
        formData.append('text', text);
        formData.append('language', 'English');

        fetch('/speak', {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Voice playback failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(() => alert('Voice playback request failed.'));
    });
}

// Auto-scroll chat box to bottom
const chatBox = document.querySelector('.chat-box');
if (chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}