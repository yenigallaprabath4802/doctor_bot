// Voice and TTS logic have been moved directly into chat.html to avoid caching issues and provide better UI feedback.

// Auto-scroll chat box to bottom
const chatBox = document.querySelector('.chat-box');
if (chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}