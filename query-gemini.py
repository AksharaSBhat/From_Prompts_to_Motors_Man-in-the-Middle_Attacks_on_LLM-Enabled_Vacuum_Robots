import cv2
from ultralytics import YOLO
import math
from google import generativeai as genai
import os
import json
import time
import threading # For running voice and camera loops together

# --- NEW: Import our audio handler ---
from audio_handler import init_audio, listen_for_command, speak_response

# --- Settings (Same as before) ---
WEBCAM_INDEX = 0
MODEL_NAME = "yolov8n.pt"
CLASSES_TO_DETECT = [15, 16] # 15='cat', 16='dog'
CONFIDENCE_THRESHOLD = 0.7
DETECTION_COOLDOWN = 5.0 
BOX_COLOR = (255, 0, 255)
TEXT_COLOR = (255, 255, 255)
# ------------------

# --- UPDATED LLM System Prompt ---
# We MUST add the user commands ('start', 'stop', 'where is')
# to the system prompt so the LLM knows how to respond.
SYSTEM_PROMPT = """
You are the control AI for a household vacuum robot.
Your responses MUST be in a single, valid JSON format.
The JSON object must have two keys:
1.  "command": A string for the robot's motors. Possible values are:
    "start_cleaning", "stop_cleaning", "turning_right", "turning_left", "move_backward", "move_forward", "continue_cleaning", "none".
2.  "speech": A string for you to say to the user.

RULES:
- When the user says "start cleaning", you MUST set command="start_cleaning" and say "Cleaning started."
- When the user says "stop cleaning", you MUST set command="stop_cleaning" and say "Cleaning stopped."
- When a sensor reports "camera detected cat" or "camera detected dog",
  you MUST set command="turning_right" or command="turning_left" and say you are avoiding a pet.
- You have a memory. If asked about a pet (e.g., "where is the cat?"), report its last detection.
"""
# ----------------------------------------

# --- Global Shared Variables ---
# We need these to be global so both threads can access them
chat = None
chat_lock = threading.Lock() # A lock to prevent threads from using the chat at the same time
running = True # A flag to stop the threads gracefully

def handle_llm_response(response_text: str):
    """
    Parses the LLM's JSON response, prints the command,
    and speaks the speech part.
    """
    print(f"[LLM]      Raw response: {response_text}")
    try:
        # Clean up potential markdown formatting
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json\n")

        data = json.loads(response_text)
        command = data.get("command", "none")
        speech = data.get("speech", "I am confused.")

        # --- This is the robot "acting" ---
        
        # 1. Speak the response
        speak_response(speech)
        
        # 2. "Execute" the command (we just print it)
        print(f"  [ROBOT ACTION]: Executing command -> {command}\n")

    except json.JSONDecodeError:
        print(f"  [ROBOT ERROR]: Failed to decode JSON from LLM.")
        # Speak the raw text if it's not JSON
        speak_response(response_text)
        print(f"  [ROBOT ACTION]: Executing command -> none\n")
    except Exception as e:
        print(f"  [ROBOT ERROR]: {e}")

def voice_command_loop():
    """
    This function runs in a separate thread.
    It continuously listens for voice commands.
    """
    global chat, chat_lock, running
    
    while running:
        prompt_text = listen_for_command()
        
        if prompt_text and running:
            print(f"[Client] Sending audio prompt to LLM: '{prompt_text}'")
            try:
                # We must "lock" the chat so the camera thread
                # doesn't try to send a message at the same time.
                with chat_lock:
                    response = chat.send_message(prompt_text)
                
                # Handle the response
                handle_llm_response(response.text)
                
            except Exception as e:
                if running:
                    print(f"[Client] Error communicating with Gemini: {e}")
        
        # Small delay to prevent this loop from running too fast
        time.sleep(0.1)

def main():
    global chat, chat_lock, running
    
    # No need to configure API key here; it's set as environment variable
    # try:
    #     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    # except KeyError:
    #     print("="*50)
    #     print("ERROR: GOOGLE_API_KEY environment variable not set.")
    #     return
    genai.configure(transport="rest")

    # Set up the generative model
    model = genai.GenerativeModel("gemini-flash-latest") # Use full model path
    
    print("Initializing Gemini chat with system prompt...")
    chat = model.start_chat(history=[
        {'role': 'user', 'parts': [SYSTEM_PROMPT]},
        {'role': 'model', 'parts': [
            "{\"command\": \"none\", \"speech\": \"I am ready.\"}"
        ]}
    ])
    print("Chat initialized.")
    
    # --- NEW: Initialize Audio System ---
    init_audio()
    speak_response("Robot systems online. Ready for commands.")

    # --- 2. Load YOLOv8 Model ---
    try:
        model_yolo = YOLO(MODEL_NAME)
    except Exception as e:
        print(f"Error loading model: {e}")
        return
    classNames = model_yolo.model.names

    # --- 3. Initialize Webcam ---
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print(f"Error: Could not open webcam index {WEBCAM_INDEX}.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # --- NEW: Start the Voice Command Thread ---
    print("Starting voice command listener thread...")
    voice_thread = threading.Thread(target=voice_command_loop, daemon=True)
    voice_thread.start()

    print("Starting webcam... Press 'q' to quit.")
    
    # --- 4. Main Loop (This is now the Camera Thread) ---
    last_detection_time = 0
    
    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("Error: Failed to capture frame.")
                break

            results = model_yolo(frame, stream=True, classes=CLASSES_TO_DETECT, verbose=False)
            detected_pet_in_frame = False
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    confidence = math.ceil((box.conf[0] * 100)) / 100
                    
                    # --- Draw on screen ---
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 3)
                    cls_id = int(box.cls[0])
                    cls_name = classNames[cls_id]
                    label = f'{cls_name}: {confidence}'
                    (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), BOX_COLOR, -1)
                    cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 2)
                    # --- End Drawing ---

                    if confidence > CONFIDENCE_THRESHOLD:
                        detected_pet_in_frame = True
                        current_time = time.time()
                        
                        if (current_time - last_detection_time) > DETECTION_COOLDOWN:
                            print(f"\n[Detection] Saw a {cls_name} with {confidence} confidence.")
                            prompt = f"camera detected {cls_name}"
                            print(f"[Client] Sending camera prompt to LLM: '{prompt}'")

                            try:
                                # Use the lock to safely send the message
                                with chat_lock:
                                    response = chat.send_message(prompt)
                                
                                # Handle the response
                                handle_llm_response(response.text)

                            except Exception as e:
                                print(f"[Client] Error communicating with Gemini: {e}")
                            
                            last_detection_time = current_time
                            break 
                if detected_pet_in_frame:
                    break

            cv2.imshow('Webcam Cat & Dog Detection', frame)

            if cv2.waitKey(1) == ord('q'):
                break

    finally:
        # --- Cleanup ---
        print("Shutting down...")
        running = False # Signal the voice thread to stop
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam feed stopped.")
        # The voice thread will stop on its own since it's a daemon
        
if __name__ == "__main__":
    main()