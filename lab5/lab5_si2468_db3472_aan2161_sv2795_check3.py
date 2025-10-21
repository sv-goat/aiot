import asyncio
import fastapi_poe as fp
import gradio as gr
import whisper
import json
import requests

PROMPT_TEMPLATE = (
    "You are a voice assistant for a smartwatch.\n"
    "When the user gives a voice command, interpret it and respond with a JSON object WITHOUT MARKDOWN FORMATTING "
    "that calls the correct smartwatch function.\n\n"
    "Available functions:\n"
    "● Turn on smartwatch screen: {name: 'screen_on', args: []}\n"
    "● Turn off smartwatch screen: {name: 'screen_off', args: []}\n"
    "● Display current time on the screen: {name: 'display_time', args: []}\n"
    "● Display a custom message on the screen: {name: 'display_message', args: [text]}\n"
    "● Set an alarm at hour:minute:second (24-hour format). This takes a timestamp, not a time interval. "
    "If the user request contains a time interval, convert it to a timestamp based on current time: "
    "{name: 'set_alarm', args: [hour, minutes]}\n"
    "● Display current location (latitude and longitude): {name: 'display_location', args: []}\n"
    "● Display weather information for the current location: {name: 'display_weather', args: []}\n\n"
    "If the request does not match any of the listed functions, answer it using your own knowledge "
    "and respond with the display_text function in this format:\n"
    "{name: 'display_text', args: [text]}.\n\n"
    "Since the smartwatch has a small display, keep your text responses under 48 characters.\n\n"
    "This prompt connects the LLM’s natural language processing with a Gradio interface, "
    "allowing users to give voice commands that are interpreted and sent to the smartwatch."
)
POE_API_KEY = 'NuDA0B76ng7Wz_uhlCnvfRAwUQZP6IAwctKxGaVoPas'

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

        # Attempt to parse as JSON
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

def process_input(audio):
    transcription = f"Placeholder for audio: {audio}"
    whisper_model = whisper.load_model("tiny.en")
    transcription = whisper_model.transcribe(audio)["text"]
    print(f"Transcription: {transcription}")

    prompt = PROMPT_TEMPLATE + f"The user's command is: {transcription}\n"

    llm_response = asyncio.run(get_llm_response(prompt))
    print(f"LLM Response: {llm_response}")

    parsed_response = parse_llm_response(llm_response)
    print(f"Parsed Response: {parsed_response}")

    # Send the CURL request to the local server
    try:
        response = requests.post("http://10.206.23.195:80/run", json=parsed_response)
        print(f"Smartwatch Response: {response.text}")
        smartwatch_response = response.text
    except Exception as e:
        print(f"Error sending request to smartwatch: {e}")
        smartwatch_response = f"Error: {e}"
    return transcription, llm_response, smartwatch_response

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
    