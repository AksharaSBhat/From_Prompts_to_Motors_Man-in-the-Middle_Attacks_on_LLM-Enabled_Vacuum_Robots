import speech_recognition as sr
from gtts import gTTS
import pygame
import io

# Initialize the recognizer
r = sr.Recognizer()

def init_audio():
    """Initializes the pygame mixer for audio playback."""
    pygame.mixer.init()
    print("Audio handler initialized.")

def listen_for_command() -> str | None:
    """
    Listens for a single command from the user via the microphone.
    Returns the transcribed text in lowercase, or None if it fails.
    """
    with sr.Microphone() as source:
        # We adjust for ambient noise *once* at the start
        # In a real robot, you'd do this more often or dynamically
        # r.adjust_for_ambient_noise(source, duration=1) 
        
        print("\n[Audio] Listening for a command...")
        r.pause_threshold = 1.0 # seconds of non-speaking audio to consider a 'phrase'
        
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
        except sr.WaitTimeoutError:
            print("[Audio] Listening timed out.")
            return None

    try:
        # Use Google's free web-based speech recognition
        text = r.recognize_google(audio)
        print(f"[Audio] User said: '{text}'")
        return text.lower()
    except sr.UnknownValueError:
        print("[Audio] Could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"[Audio] Google API error: {e}")
        return None

def speak_response(text: str):
    """
    Converts the given text to speech and plays it on the speakers.
    """
    if not text:
        return
        
    print(f"[Audio] Speaking: '{text}'")
    try:
        # Create TTS object
        tts = gTTS(text=text, lang='en')
        
        # Save to an in-memory file
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        # Load the in-memory file into pygame mixer
        pygame.mixer.music.load(fp)
        pygame.mixer.music.play()
        
        # Wait for the audio to finish playing
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
    except Exception as e:
        print(f"[Audio] Error in text-to-speech: {e}")

# You can run this file directly to test your mic and speakers
if __name__ == "__main__":
    init_audio()
    
    print("Testing text-to-speech...")
    speak_response("Hello, this is a speaker test.")
    
    print("\nTesting microphone...")
    speak_response("Please say something for the microphone test.")
    command = listen_for_command()
    if command:
        speak_response(f"I heard you say: {command}")
    else:
        speak_response("I didn't hear anything.")