from contextlib import contextmanager
import os
import time
import speech_recognition as sr
from gtts import gTTS
import pygame
import io

r = sr.Recognizer()


@contextmanager
def suppress_alsa_warnings():
    devnull = open(os.devnull, "w")
    old_stderr = os.dup(2)
    os.dup2(devnull.fileno(), 2)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        devnull.close()


def init_audio():
    """Initializes the pygame mixer for audio playback."""
    pygame.mixer.init()
    print("Audio handler initialized.")


def listen_for_command() -> str | None:
    """
    Listens for a single command from the user via the microphone.
    Returns the transcribed text in lowercase, or None if it fails.
    """
    with suppress_alsa_warnings():
        with sr.Microphone() as source:
            print("\n[Audio] Listening for a command...")
            r.pause_threshold = 1.0

            try:
                audio = r.listen(source, timeout=1, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                print("[Audio] Listening timed out.")
                return None

        try:
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

    with suppress_alsa_warnings():
        print(f"[Audio] Speaking: '{text}'")
        try:
            tts = gTTS(text=text, lang="en")
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            pygame.mixer.music.load(fp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.001)

        except Exception as e:
            print(f"[Audio] Error in text-to-speech: {e}")


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
