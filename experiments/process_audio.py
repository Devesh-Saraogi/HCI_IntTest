import os
import base64
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import langchain_google_genai.chat_models

# Monkey patch to fix max_retries bug for non-gemini models in langchain-google-genai
_original_chat_with_retry = langchain_google_genai.chat_models._chat_with_retry
def _patched_chat_with_retry(*args, **kwargs):
    kwargs.pop("max_retries", None)
    kwargs.pop("timeout", None)
    return _original_chat_with_retry(*args, **kwargs)
langchain_google_genai.chat_models._chat_with_retry = _patched_chat_with_retry

load_dotenv()

def run_audio(wav_file_path, output_json_path):
    # Initialize the model
    target_model = ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        temperature=0.0
    )

    print(f"Reading audio file: {wav_file_path}")
    with open(wav_file_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

    print(f"Sending audio to gemma-4-31b-it...")
    
    # Construct the message with the audio
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": "Please process this audio file."
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:audio/wav;base64,{audio_base64}"}
            }
        ]
    )
    
    try:
        response = target_model.invoke([message])
        output_text = response.content
        print("Received response from model.")
    except Exception as e:
        print(f"Error during API call: {e}")
        output_text = f"Error: {e}"

    # Write output to JSON
    result = {
        "model": "gemma-4-31b-it",
        "audio_file": wav_file_path,
        "response": output_text
    }

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
        
    print(f"Output saved to {output_json_path}")

if __name__ == "__main__":
    wav_file = "experiments/tts.wav"
    out_file = "experiments/output.json"
    run_audio(wav_file, out_file)
