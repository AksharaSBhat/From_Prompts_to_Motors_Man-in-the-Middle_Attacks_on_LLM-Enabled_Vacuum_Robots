# From Prompts to Motors: MITM Attacks on LLM-Enabled Robots
This project is a practical implementation based on the research paper [From Prompts to Motors: Man-in-the-Middle Attacks on LLM-Enabled Vacuum Robots](https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=11108294) (DOI: 10.1109/ACCESS.2025.3595424).

It demonstrates how a Man-in-the-Middle (MITM) attacker can intercept and manipulate the communication between an "LLM-enabled robot" and its cloud-based LLM (in this case, Google Gemini) to inject malicious prompts or modify the LLM's responses.

## Security & Ethics Warning
This project contains code for performing network attacks for educational and research purposes
ONLY.
- DO NOT run these scripts on any network or device you do not own or have explicit permission to test.
- It is STRONGLY RECOMMENDED to run this entire project within a controlled, isolated virtual machine (VM) environment to prevent unintended consequences.
- The authors are not responsible for any damage or misuse of this code.

## Project Overview
This implementation consists of two main parts:

1. **The "Robot" Client ( `query-gemini.py` ):** This script simulates the robot. It uses the microphone to listen for voice commands (e.g., "start cleaning") and the webcam to detect objects (e.g., "cat", "dog") using YOLOv8. It sends this information as prompts to the Google Gemini API and "acts" on the JSON response it receives.
2. **The "Attacker" Proxy ( `mitmproxy-addon.py` ):** This is an addon script for mitmproxy. It intercepts all traffic between the "robot" and the Google API. Based on the attack scenario, it can modify outgoing prompts (Prompt Injection) or incoming responses (Output Manipulation) in real-time.

## Project Files
- `query-gemini.py` : The main client script for the "robot".
- `audio_handler.py` : A helper module for handling speech-to-text and text-to-speech.
- `mitmproxy-addon.py` : The attacker's addon script for mitmproxy.
- `From_Prompts_to_Motors...pdf` : The original research paper.

## Dependencies & Installation
### 1. System Dependencies (Linux/Debian-based)
First, update your package list and install the system-level library required for `PyAudio` :
```bash
sudo apt-get update
sudo apt-get install python3-pyaudio
```

### 2. mitmproxy
You must install mitmproxy to act as the attacker's proxy. Please follow the official installation
instructions from their website:
- **mitmproxy Official Website:** https://mitmproxy.org/

### 3. Python Packages
It is highly recommended to use a Python virtual environment.
```bash
# Create a virtual environment
python3 -m venv venv
# Activate it
source venv/bin/activate
# Install all required pip packages
pip install SpeechRecognition gTTS pygame PyAudio
pip install ultralytics
pip install google-genai
pip install google-generativeai
pip install google
pip install python-dotenv
```

## Configuration & Usage
Follow these steps to set up and run the simulation.
### 1. Configure the "Robot" Client
The robot script ( `query-gemini.py` ) requires a Google Gemini API key.
Set this key as an environment variable in your terminal:
`export GEMINI_API_KEY="YOUR_API_KEY_HERE"`
You should the following line to you shell's run-commands file and restart the shell.
`export GRPC_DEFAULT_SSL_ROOTS_FILE_PATH="/etc/ssl/certs/ca-certificates.crt"`

### 2. Configure the "Attacker" Proxy
The `mitmproxy-addon.py` script is used to define the attack scenarios. Look into the mitmproxy [documentation](https://docs.mitmproxy.org/stable/api/mitmproxy/http.html) on different event hooks and modify the script accordinlgy for a custom attack.

### 3. Run the Attack Simulation
You will need two separate terminal windows, ideally on two separate machines or VMs (one for the
attacker, one for the robot).
#### Step A: On the Attacker Machine
1. Start mitmproxy with the addon script. This will launch the proxy server (usually on port 8080)
and its console interface.
    `mitmproxy --mode transparent -s mitmproxy-addon.py --set scenario="your desired scenario from the paper"`

#### Step B: On the "Robot" Machine
1. **Route Traffic Through the Proxy:** You must configure this machine to send all its internet traffic through the `mitmproxy` instance.

   - Find the IP address of the attacker machine (e.g., `192.168.1.10`).
   - Set the system-wide HTTP and HTTPS proxy on the robot machine to point to the attacker's IP and port (e.g., `http://192.168.1.10:8080` and `https://192.168.1.10:8080`).

2. **Install the Proxy Certificate:** Your robot machine will not trust the proxy's HTTPS connection by default. You must install the `mitmproxy` CA certificate.

   - With the proxy running, visit `http://mitm.it` in a browser on the robot machine.
   - Follow the instructions to download and install the certificate for your operating system.

---

### Step C: Run the Robot Client

1. Once the proxy is set up and the certificate is installed, go to the terminal on the robot machine.  
2. Ensure your `GOOGLE_API_KEY` is set (from Step 1).  
3. Activate your virtual environment:

   ```bash
   source venv/bin/activate
    ```
4. Run the robot script:
`python query-gemini.py`

**Observe the Attack**
The Attacker's Terminal (running mitmproxy ) will show all intercepted network traffic. You will
see the mitmproxy-addon.py script printing messages as it modifies requests or responses.
The Robot's Terminal (running query-gemini.py ) will show the result of the attack. You will see it receive manipulated commands (e.g., "I just ran over the cat.") instead of the real ones.

## License
This project is provided for academic and research purposes. Please consider adding an open-source license (e.g., MIT) if you plan to distribute or build upon this work.