import cv2
from ultralytics import YOLO
import time
import threading
import queue
import json
from google import generativeai as genai
import dotenv
from audio_handler import init_audio, listen_for_command, speak_response

dotenv.load_dotenv()

WEBCAM_INDEX = 0
MODEL_NAME = "yolov8n_openvino_model"  # "yolov8n.pt"
CLASSES = {15: "cat", 16: "dog"}
CONFIDENCE_THRESHOLD = 0.7
DETECTION_COOLDOWN = 5.0
BOX_COLOR = (255, 0, 255)
TEXT_COLOR = (255, 255, 255)

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

chat = None
running = True
llm_queue = queue.Queue()
voice_queue = queue.Queue()


def handle_llm_response(response_text: str):
    """Parses and acts on Gemini JSON response."""
    print(f"[LLM] Raw response: {response_text}")
    try:
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json\n")

        data = json.loads(response_text)
        command = data.get("command", "none")
        speech = data.get("speech", "I am confused.")

        voice_queue.put(speech)
        print(f"[ROBOT ACTION]: Executing command -> {command}\n")

    except json.JSONDecodeError:
        print("[ROBOT ERROR]: Invalid JSON from LLM.")
        voice_queue.put(response_text)
    except Exception as e:
        print(f"[ROBOT ERROR]: {e}")


def llm_thread_func():
    """Handles all LLM communication asynchronously.
    Discards old commands, always processes only the latest one.
    """
    global running

    while running:
        prompt = llm_queue.get()
        while not llm_queue.empty():
            try:
                prompt = llm_queue.get_nowait()
                llm_queue.task_done()
            except queue.Empty:
                break
        try:
            print(f"[Client] Sending prompt to LLM: '{prompt}'")
            if chat is None:
                raise RuntimeError("chat not initialised")

            response = chat.send_message(prompt)
            handle_llm_response(response.text)
        except Exception as e:
            print(f"[Client] Error communicating with Gemini: {e}")
        finally:
            llm_queue.task_done()


def voice_thread_func():
    """Listens for voice commands and enqueues them for LLM."""
    global running
    while running:
        response = ""
        try:
            response = voice_queue.get_nowait()
            while not voice_queue.empty():
                response += "and " + voice_queue.get_nowait()
                voice_queue.task_done()
        except queue.Empty:
            pass

        if response:
            try:
                speak_response(response)
            finally:
                voice_queue.task_done()

        try:
            prompt_text = listen_for_command()
            if prompt_text and running:
                print(f"[Voice] Heard: '{prompt_text}'")
                llm_queue.put(prompt_text)
        except Exception as e:
            print(f"[Voice] Error: {e}")


def main():
    global chat, running

    genai.configure(transport="rest")
    model = genai.GenerativeModel("gemini-flash-latest")

    chat = model.start_chat(
        history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ['{"command":"none","speech":"I am ready."}']},
        ]
    )

    init_audio()
    voice_queue.put("Robot systems online. Ready for commands.")

    model_yolo = YOLO(MODEL_NAME)
    threading.Thread(target=llm_thread_func, daemon=True).start()
    threading.Thread(target=voice_thread_func, daemon=True).start()

    cap = cv2.VideoCapture(WEBCAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("Camera started. Press 'q' to quit.")

    last_detection_time = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            orig_h, orig_w = frame.shape[:2]

            input_w, input_h = 640, 640
            input_frame = cv2.resize(frame, (input_w, input_h))

            results = model_yolo(
                input_frame,
                imgsz=(input_w, input_h),
                stream=True,
                classes=list(CLASSES.keys()),
                verbose=False,
            )
            current_time = time.time()

            scale_x = orig_w / input_w
            scale_y = orig_h / input_h

            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    if conf < CONFIDENCE_THRESHOLD:
                        continue

                    cls_id = int(box.cls[0])
                    cls_name = CLASSES[cls_id]

                    bx = box.xyxy[0]
                    x1 = int(round(float(bx[0]) * scale_x))
                    y1 = int(round(float(bx[1]) * scale_y))
                    x2 = int(round(float(bx[2]) * scale_x))
                    y2 = int(round(float(bx[3]) * scale_y))
                    x1 = max(0, min(x1, orig_w - 1))
                    x2 = max(0, min(x2, orig_w - 1))
                    y1 = max(0, min(y1, orig_h - 1))
                    y2 = max(0, min(y2, orig_h - 1))

                    label = f"{cls_name}: {conf:.2f}"

                    cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
                    (tw, th), bl = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                    )
                    ty = y1 - 6 if y1 - th - bl > 0 else y1 + th + 6
                    cv2.rectangle(
                        frame, (x1, ty - th - bl), (x1 + tw, ty + bl), BOX_COLOR, -1
                    )
                    cv2.putText(
                        frame,
                        label,
                        (x1, ty),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        TEXT_COLOR,
                        2,
                    )

                    if (current_time - last_detection_time) > DETECTION_COOLDOWN:
                        print(f"[Detection] Saw a {cls_name} ({conf:.2f})")
                        llm_queue.put(f"camera detected {cls_name}")
                        last_detection_time = current_time

            cv2.imshow("Pet Detection", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        pass

    finally:
        print("Shutting down...")
        running = False
        cap.release()
        cv2.destroyAllWindows()
        print("All systems stopped.")


if __name__ == "__main__":
    main()
