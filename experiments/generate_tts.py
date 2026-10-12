import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Reconfigure console encoding for Windows terminals to display Hindi characters without crashing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration Block
# ---------------------------------------------------------------------------
# Edit this line with your desired "Chalu Hindi" (colloquial street Hindi) text:
DEFAULT_CHALU_HINDI_LINE = (
    "ये एक कंट्रोल सिक्योरिटी टेस्ट है।"
)

# Target TTS model
MODEL_NAME = "canopylabs/orpheus-arabic-saudi"

# Available voices for this model: 'abdullah', 'fahad', 'sultan', 'lulwa', 'aisha', 'noura'
DEFAULT_VOICE = "abdullah"

# Output audio file path
DEFAULT_OUTPUT_FILE = "experiments/tts.wav"
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Finds the root directory containing .env or experiments folder."""
    current = Path(__file__).resolve().parent
    if (current / ".env").exists() or (current / "experiments").exists():
        return current
    if (current.parent / ".env").exists():
        return current.parent
    return current


def load_environment():
    """Loads .env file from project root or parent directories."""
    root = get_project_root()
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


def text_to_speech(
    text: str,
    output_path: str = DEFAULT_OUTPUT_FILE,
    voice: str = DEFAULT_VOICE,
    model: str = MODEL_NAME
) -> str:
    """
    Converts input text (Chalu Hindi) to speech using canopylabs/orpheus-arabic-saudi on Groq.
    
    Args:
        text: The text to convert to audio.
        output_path: Where to save the generated WAV file.
        voice: Voice persona ('abdullah', 'fahad', 'sultan', 'lulwa', 'aisha', 'noura').
        model: Model identifier on Groq.
        
    Returns:
        The path of the generated audio file.
    """
    load_environment()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found in environment or .env file. "
            "Please ensure GROQ_API_KEY is defined in your .env file."
        )

    # Resolve output path relative to workspace root if running from elsewhere
    root = get_project_root()
    target_path = Path(output_path)
    if not target_path.is_absolute():
        # If output_path is 'experiments/tts.wav' and we're inside 'experiments/', avoid double nesting
        if Path.cwd().name == "experiments" and target_path.parts[0] == "experiments":
            target_path = Path.cwd() / target_path.name
        else:
            target_path = root / target_path

    # Ensure destination folder exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Orpheus TTS Configuration")
    print("=" * 60)
    print(f"Model:       {model}")
    print(f"Voice:       {voice}")
    print(f"Characters:  {len(text)}")
    print(f"Input Text:  {text}")
    print(f"Output File: {target_path}")
    print("-" * 60)
    print("Sending request to Groq Speech API...")

    client = Groq(api_key=api_key)

    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice.lower(),
            input=text,
            response_format="wav"
        )

        response.write_to_file(str(target_path))

        file_size_bytes = target_path.stat().st_size
        file_size_kb = file_size_bytes / 1024.0
        print(f"Successfully generated audio file: {target_path}")
        print(f"File Size:   {file_size_kb:.2f} KB ({file_size_bytes:,} bytes)")
        print("=" * 60)
        return str(target_path)

    except Exception as e:
        print(f"Error generating TTS audio: {e}", file=sys.stderr)
        raise


def load_text_from_json(json_file_path: str, prompt_id: str = None, prompt_key: str = "hindi_prompt") -> str:
    """Helper to extract a Hindi prompt from a JSON experiment file (e.g., exp1.json)."""
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        if prompt_id:
            for item in data:
                if item.get("id") == prompt_id:
                    return item.get(prompt_key, "")
            raise ValueError(f"Prompt with id '{prompt_id}' not found in {json_file_path}")
        else:
            # Pick first non-empty item
            for item in data:
                if item.get(prompt_key):
                    return item.get(prompt_key)
            raise ValueError(f"No entry with non-empty '{prompt_key}' found in {json_file_path}")
    elif isinstance(data, dict):
        if prompt_id and prompt_id in data:
            return data[prompt_id].get(prompt_key, "")
        return data.get(prompt_key, "")

    raise ValueError(f"Unable to parse format of {json_file_path}")


def update_ultimate_json_with_tts(audio_path: str, voice: str, model: str, text: str):
    """Updates ultimate.json with the generated audio details."""
    root = get_project_root()
    ultimate_path = root / "experiments" / "ultimate.json"
    latest_path = root / "experiments" / "latest_ultimate.json"
    
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else None

    # Update ultimate.json
    if ultimate_path.exists():
        try:
            with open(ultimate_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list) and records:
                # Find matching record or take latest
                target_rec = records[-1]
                for rec in reversed(records):
                    if rec.get("chalu_hindi") == text:
                        target_rec = rec
                        break
                target_rec["audio_file"] = str(audio_path)
                target_rec["tts_model"] = model
                target_rec["tts_voice"] = voice
                target_rec["tts_generated"] = True
                target_rec["tts_size_bytes"] = file_size
                target_rec["status"] = "tts_completed"
                with open(ultimate_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Notice: Could not update ultimate.json: {e}")

    # Update latest_ultimate.json
    if latest_path.exists():
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                rec = json.load(f)
            rec["audio_file"] = str(audio_path)
            rec["tts_model"] = model
            rec["tts_voice"] = voice
            rec["tts_generated"] = True
            rec["tts_size_bytes"] = file_size
            rec["status"] = "tts_completed"
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Convert a line in textual Chalu Hindi to tts.wav using canopylabs/orpheus-arabic-saudi"
    )
    parser.add_argument(
        "--text", "-t",
        type=str,
        default=None,
        help="Textual Chalu Hindi line to convert"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Destination WAV file path (default: {DEFAULT_OUTPUT_FILE})"
    )
    parser.add_argument(
        "--voice", "-v",
        type=str,
        default=DEFAULT_VOICE,
        choices=["abdullah", "fahad", "sultan", "lulwa", "aisha", "noura"],
        help=f"Voice persona to use (default: {DEFAULT_VOICE})"
    )
    parser.add_argument(
        "--from-file", "-f",
        type=str,
        default=None,
        help="Path to text file containing Chalu Hindi line (e.g. experiments/chalu_hindi.txt)"
    )
    parser.add_argument(
        "--from-ultimate", "-u",
        action="store_true",
        help="Load the latest Chalu Hindi prompt directly from experiments/ultimate.json"
    )
    parser.add_argument(
        "--from-json",
        type=str,
        default=None,
        help="Path to experiment JSON file (e.g. experiments/exp1.json) to read the prompt from"
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Prompt ID to read when using --from-json (e.g. w4hngc)"
    )

    args = parser.parse_args()

    # Determine input text
    text = None
    if args.from_json:
        text = load_text_from_json(args.from_json, prompt_id=args.id)
    elif args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
    elif args.from_ultimate:
        root = get_project_root()
        latest_path = root / "experiments" / "latest_ultimate.json"
        if latest_path.exists():
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = data.get("chalu_hindi", "")
    elif args.text:
        text = args.text
    else:
        # Check if ultimate.json has a prompt ready
        root = get_project_root()
        latest_path = root / "experiments" / "latest_ultimate.json"
        if latest_path.exists():
            try:
                with open(latest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("chalu_hindi"):
                    text = data.get("chalu_hindi")
                    print("Notice: Automatically loaded latest Chalu Hindi from experiments/latest_ultimate.json")
            except Exception:
                pass

        if not text:
            text = DEFAULT_CHALU_HINDI_LINE

    if not text.strip():
        print("Error: Input text is empty.", file=sys.stderr)
        sys.exit(1)

    try:
        out_wav = text_to_speech(
            text=text,
            output_path=args.output,
            voice=args.voice,
            model=MODEL_NAME
        )
        update_ultimate_json_with_tts(out_wav, args.voice, MODEL_NAME, text)
    except Exception as exc:
        print(f"Failed to create speech file: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
