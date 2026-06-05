try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False

import threading
import os

# Pyttsx3 is not thread-safe, use a lock
tts_lock = threading.Lock()

def generate_tts_audio_file(text, output_path, voice_style='male'):
    """
    Generate an audio file using pyttsx3 for the given text.
    voice_style can be 'male' (for the Mahesh Babu style) or 'female' (Keerthy Suresh style).
    Returns True if successful, False otherwise.
    """
    if not PYTTSX3_AVAILABLE:
        print('TTS Error: pyttsx3 is not installed.')
        return False

    with tts_lock:
        try:
            # We must re-init engine in the thread or it can crash
            engine = pyttsx3.init()
            engine.setProperty('rate', 155) 
            
            voices = engine.getProperty('voices') or []
            
            preferred = None
            if voice_style == 'female':
                for v in voices:
                    name_lower = (v.name or '').lower()
                    if 'zira' in name_lower or 'female' in name_lower:
                        preferred = v.id
                        break
            else:
                for v in voices:
                    name_lower = (v.name or '').lower()
                    if 'david' in name_lower or 'male' in name_lower:
                        preferred = v.id
                        break
            
            if not preferred and voices:
                preferred = voices[0].id

            if preferred:
                engine.setProperty('voice', preferred)

            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return True
        except Exception as e:
            print(f"TTS File Generation Error: {e}")
            return False

def text_to_speech(text, language='English'):
    """
    Convert text to speech using pyttsx3.
    Supports English, Hindi, and Telugu when available.
    """
    if not PYTTSX3_AVAILABLE:
        print('TTS Error: pyttsx3 is not installed.')
        return False

    with tts_lock:
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
