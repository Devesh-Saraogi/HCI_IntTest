import os
import base64
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def run_audio(wav_file_path, output_json_path):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not found.")
        return

    # Using the direct REST API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={api_key}"
    
    print(f"Reading audio file: {wav_file_path}")
    with open(wav_file_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Please process this audio file."},
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": audio_base64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0
        }
    }

    print("Sending audio to gemma-4-31b-it via REST...")
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        try:
            output_text = data["candidates"][0]["content"]["parts"][0]["text"]
            print("Received response from model.")
        except (KeyError, IndexError) as e:
            output_text = f"Failed to parse response: {data}"
    else:
        print(f"Error {response.status_code}: {response.text}")
        output_text = f"Error {response.status_code}: {response.text}"

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
    out_file = "experiments/output_rest.json"
    run_audio(wav_file, out_file)
