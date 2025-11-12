import asyncio
import fastapi_poe as fp
import gradio as gr
import whisper
import json
import requests
import re

whisper_model = whisper.load_model("tiny.en")  # global


PROMPT_TEMPLATE = (
    "You are a voice assistant for a smartwatch.\n"
    "When the user gives a voice command, interpret it and respond with a JSON object WITHOUT MARKDOWN FORMATTING "
    "that calls the correct smartwatch function.\n\n"
    "Available functions:\n"
    '● Turn on smartwatch screen: {name: "screen_on", args: []}\n'
    '● Turn off smartwatch screen: {name: "screen_off", args: []}\n'
    '● Display current time on the screen: {name: "display_time", args: []}\n'
    '● Display a custom message on the screen: {name: "display_message", args: ["text"]}\n'
    '● Set an alarm at hour:minute:second (24-hour format). This takes a timestamp, not a time interval. '
    'If the user request contains a time interval, convert it to a timestamp based on current time: '
    '{name: "set_alarm", args: [hour, minutes]}\n'
    '● Display current location (latitude and longitude): {name: "display_location", args: []}\n'
    '● Display weather information for the current location: {name: "display_weather", args: []}\n'
    "● Run on-device HAR via ESP32 + LLM: {name: 'classify_har', args: []}\n\n"
    "If the user asks to 'classify HAR data', 'recognize my activity', or similar, use {name:'classify_har', args: []}.\n"
    "If the request does not match any of the listed functions, answer it using your own knowledge "
    "and respond with the display_text function in this format:\n"
    "{name: 'display_text', args: [text]}.\n\n"
    "NOTE: ENCLOSE ALL PROPERTIES IN DOUBLE QUOTES TO ENSURE VALID JSON.\n\n"
    "Since the smartwatch has a small display, keep your text responses under 48 characters.\n\n"
    "This prompt connects the LLM’s natural language processing with a Gradio interface, "
    "allowing users to give voice commands that are interpreted and sent to the smartwatch."
)

POE_API_KEY = "sEIxZsHJyHVpSZh3WjCzOGqnitGyaGXzoUz_Ls2oJ64"

# ==== ESP32 / HAR helpers (from checkpoint 2, lightly adapted) ====

ESP_IP = "192.168.1.154"   # <-- set your device IP here (or load from env)

def call_esp32(esp_ip, function_name, args=[]):
    import requests, json
    url = f"http://{esp_ip}/run"
    payload = {"name": function_name, "args": args}
    try:
        timeout = 15 if function_name == "get_har_data" else 5
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("result") if data.get("ok") else None
    except Exception as e:
        print(f"[ESP32 Error] {e}")
        return None

def format_esp32_prompt(sensor_data, attachment_location, question):
    acc_x = sensor_data.get("acc_x", [])
    acc_y = sensor_data.get("acc_y", [])
    acc_z = sensor_data.get("acc_z", [])
    fx = ", ".join([f"{v:.2f}" for v in acc_x[:10]]) + ", ..."
    fy = ", ".join([f"{v:.2f}" for v in acc_y[:10]]) + ", ..."
    fz = ", ".join([f"{v:.2f}" for v in acc_z[:10]]) + ", ..."
    return f"""Device: ESP32 Smartwatch
Attached Location: {attachment_location}
Candidate Activities: WALKING, WALKING_UPSTAIRS, WALKING_DOWNSTAIRS, SITTING, STANDING, LAYING

Data (3-axis Accelerometer ONLY):
Accelerometer X over time: [{fx}]
Accelerometer Y over time: [{fy}]
Accelerometer Z over time: [{fz}]

Question: {question}
"""

async def classify_har_flow(esp_ip, get_llm_response):
    # 1) pull window from ESP32
    sensor_data = call_esp32(esp_ip, "get_har_data")
    if not sensor_data or "acc_x" not in sensor_data:
        return "HAR fetch failed"

    # 2) build prompt (CoT request, end with explicit label ask)
    cot_question = (
        "Explain your reasoning step by step, then give only the activity "
        "label as the final answer (e.g., '...Final Answer: WALKING')."
    )
    prompt = format_esp32_prompt(sensor_data, "Wrist", cot_question)

    # 3) ask LLM
    llm_response = await get_llm_response(prompt)
    if not llm_response:
        return "LLM error"

    # 4) parse label (case-insensitive scan)
    labels = ["WALKING","WALKING_UPSTAIRS","WALKING_DOWNSTAIRS","SITTING","STANDING","LAYING"]
    upper = llm_response.upper()
    print(f"LLM HAR Response: {llm_response}")
    
    # Extract predicted label
    # Predicted label usually comes after "FINAL ANSWER:". So, use that to find it using regex
    match = re.search(r"final answer:\s*([A-Z_]+)", llm_response, re.IGNORECASE)
    if match:
        predicted = match.group(1)
    else:
        predicted = "Unknown"

    # 5) display on OLED (use display_text or display_message per your ESP firmware)
    call_esp32(esp_ip, "display_text", [predicted])  # or "display_message"
    return predicted

def parse_llm_response(response_text: str):
    """
    Safely parse the LLM's output as JSON. If parsing fails,
    return a fallback action using display_text.
    """
    try:
        # Try to strip markdown code fences if they exist
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        # Replace single quotes with double quotes for valid JSON
        cleaned = cleaned.replace("'", '"')
        
        # Parse as JSON
        data = json.loads(cleaned)
        if isinstance(data, dict) and "name" in data and "args" in data:
            return data
        
        # If structure is wrong
        raise ValueError("Invalid JSON structure")
    
    except Exception as e:
        print(e)
        # Graceful fallback — show an error message on the smartwatch
        return {"name": "display_text", "args": ["Command error"]}

async def get_llm_response(prompt):
    message = fp.ProtocolMessage(role="user", content=prompt)
    full_response = ""
    async for partial in fp.get_bot_response(messages=[message],
    bot_name='GPT-4o-Mini',
    api_key=POE_API_KEY):
        full_response += partial.text
    return full_response

async def process_input_async(audio):
    """Async version that handles both voice commands and HAR classification."""
    transcription = whisper_model.transcribe(audio)["text"]
    print(f"🎤 Transcription: {transcription}")

    prompt = PROMPT_TEMPLATE + f"The user's command is: {transcription}\n"

    llm_response = await get_llm_response(prompt)
    print(f"🤖 LLM Response: {llm_response}")

    parsed_response = parse_llm_response(llm_response)
    print(f"📋 Parsed Response: {parsed_response}")

    # NEW: intercept the classify_har command 🎯
    if isinstance(parsed_response, dict) and parsed_response.get("name") == "classify_har":
        try:
            predicted = await classify_har_flow(ESP_IP, get_llm_response)
            smartwatch_response = f"🏃 HAR: {predicted}"
        except Exception as e:
            smartwatch_response = f"❌ HAR error: {e}"
        return transcription, llm_response, smartwatch_response

    # Send the command to the ESP device 📡
    try:
        response = requests.post(f"http://{ESP_IP}:80/run", json=parsed_response)
        print(f"⌚ Smartwatch Response: {response.text}")
        smartwatch_response = response.text
    except Exception as e:
        print(f"❌ Error sending request to smartwatch: {e}")
        smartwatch_response = f"Error: {e}"
    return transcription, llm_response, smartwatch_response

def process_input(audio):
    """Wrapper that Gradio can call (sync -> async)."""
    return asyncio.run(process_input_async(audio))

if __name__ == "__main__":

    ui = gr.Interface(
        inputs=[
            gr.Audio(sources=["microphone"], type="filepath", label="Voice Input"),
        ],
        fn=process_input,
        outputs=[
            gr.Textbox(label="Transcription/Input"),
            gr.Textbox(label="LLM Response"),
            gr.Textbox(label="Smartwatch Response")
        ],
        title="Voice Assistant",
        description="My capabilities: XXX",
        allow_flagging="never"
    )
    ui.launch(debug=False, share=True)