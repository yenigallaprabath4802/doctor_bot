try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False


def text_to_speech(text, language='English'):
    """
    Convert text to speech using pyttsx3.
    Supports English, Hindi, and Telugu when available.
    """
    if not PYTTSX3_AVAILABLE:
        print('TTS Error: pyttsx3 is not installed.')
        return False

    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)

        voices = engine.getProperty('voices') or []
        if not voices:
            print('TTS Error: no voices available.')
            return False

        preferred = None
        language_lower = language.lower()
        if 'hindi' in language_lower or language_lower == 'hi':
            search_terms = ['hindi', 'hin', 'hi']
        elif 'telugu' in language_lower or language_lower == 'te':
            search_terms = ['telugu', 'tel', 'te']
        else:
            search_terms = ['english', 'en']

        for voice in voices:
            voice_name = (voice.name or '').lower()
            voice_id = (voice.id or '').lower()
            if any(term in voice_name or term in voice_id for term in search_terms):
                preferred = voice.id
                break

        if preferred:
            engine.setProperty('voice', preferred)

        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"TTS Error: {e}")
        return False

def speech_to_text_browser():
    """
    Speech-to-text is handled client-side via Web Speech API.
    This is a placeholder for potential server-side implementation.
    """
    return None
