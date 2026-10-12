import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

# Ensure console supports UTF-8 on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration Block
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "experiments" else CURRENT_DIR

DEFAULT_EXP_JSON      = str(CURRENT_DIR / "exp1.json")
DEFAULT_ULTIMATE_JSON = str(CURRENT_DIR / "ultimate.json")
DEFAULT_LATEST_JSON   = str(CURRENT_DIR / "latest_ultimate.json")

# Target model to evaluate against
TARGET_MODEL = "gemini-2.5-flash"

# Fields written into ultimate.json for the text baseline
TEXT_RESPONSE_FIELD = "text_baseline_response"
TEXT_MODEL_FIELD    = "text_baseline_model"
# ---------------------------------------------------------------------------


def load_environment():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


def query_target_text_model(prompt_text: str, model_name: str = TARGET_MODEL) -> str:
    """Sends English prompt as plain text to the target Gemini model and returns response."""
    load_environment()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment or .env file.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt_text.strip()}]}],
        "generationConfig": {"temperature": 0.7}
    }

    print(f"-> Sending text prompt to target model '{model_name}'...")
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            return f"Failed to parse response structure: {data}"
    else:
        return f"Error {response.status_code}: {response.text}"


def load_ultimate_json(path: str) -> list:
    p = Path(path)
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            content = json.load(f)
        return content if isinstance(content, list) else [content]
    except Exception as e:
        print(f"Warning: Could not read {path}: {e}", file=sys.stderr)
    return []


def save_ultimate_json(records: list, path: str, latest_record: dict = None):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"-> Saved ultimate JSON: {p} (Total entries: {len(records)})")

    if latest_record is not None:
        latest_path = Path(DEFAULT_LATEST_JSON)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(latest_record, f, indent=2, ensure_ascii=False)
        print(f"-> Updated latest_ultimate.json: {latest_path}")


def update_record_in_ultimate(
    record_id: str,
    update_fields: dict,
    ultimate_json_path: str = DEFAULT_ULTIMATE_JSON
) -> dict:
    """
    Finds the record with record_id in ultimate.json and merges update_fields into it.
    If the ID does not exist, creates a new entry. Returns the updated record.
    """
    records = load_ultimate_json(ultimate_json_path)
    target = None
    for i, item in enumerate(records):
        if item.get("id") == record_id:
            records[i] = {**item, **update_fields}
            target = records[i]
            break

    if target is None:
        new_record = {"id": record_id, **update_fields}
        records.append(new_record)
        target = new_record
        print(f"  Notice: ID '{record_id}' not found in ultimate.json -- creating new entry.")

    save_ultimate_json(records, ultimate_json_path, latest_record=target)
    return target


def run_text_baseline_for_prompt(
    item: dict,
    model_name: str = TARGET_MODEL,
    ultimate_json_path: str = DEFAULT_ULTIMATE_JSON
) -> dict:
    """
    Runs a single prompt through the text baseline pipeline:
      1. Extract English prompt from the item dict
      2. Send as plain text to the target model
      3. Merge the response into ultimate.json under text_baseline_response
    """
    prompt_id = item.get("id", "unknown")
    english_prompt = (
        item.get("english_prompt")
        or item.get("text_prompt")
        or item.get("english_audio_prompt")
        or ""
    ).strip()

    if not english_prompt:
        print(f"  Warning: No English prompt found for ID '{prompt_id}'. Skipping.", file=sys.stderr)
        return item

    print("\n" + "=" * 70)
    print(f"TEXT BASELINE: Processing Prompt [{prompt_id}]")
    print("=" * 70)
    print(f"Model       : {model_name}")
    print(f"English Input:\n{english_prompt}\n")

    response_text = query_target_text_model(english_prompt, model_name=model_name)

    print("\n" + "-" * 70)
    print(f"TARGET MODEL RESPONSE ({model_name}):")
    print("-" * 70)
    print(response_text)
    print("-" * 70 + "\n")

    update_fields = {
        TEXT_RESPONSE_FIELD: response_text,
        TEXT_MODEL_FIELD: model_name,
        "text_baseline_timestamp": datetime.now().isoformat(),
    }
    # Preserve existing 'completed' status from audio pipeline if present
    if item.get("status") != "completed":
        update_fields["status"] = "text_baseline_completed"

    updated = update_record_in_ultimate(prompt_id, update_fields, ultimate_json_path)
    return updated


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Text Baseline Runner: Send English prompts directly as text to the target\n"
            "Gemini model and record responses in ultimate.json.\n\n"
            "This acts as a comparison baseline for the audio pipeline (run_full_pipeline.py).\n"
            "The same prompts are evaluated via plain text instead of Chalu Hindi TTS audio."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from-json",
        type=str,
        default=DEFAULT_EXP_JSON,
        help=f"Source experiment JSON file (default: {DEFAULT_EXP_JSON})",
    )
    parser.add_argument(
        "--from-ultimate",
        action="store_true",
        help="Read prompts from ultimate.json instead of exp1.json.",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Process only the prompt with this ID (e.g. w4hngc).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process ALL prompts in the source JSON file sequentially.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Run a custom one-off English text prompt (bypasses JSON source).",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=TARGET_MODEL,
        help=f"Gemini model to use as the target (default: {TARGET_MODEL})",
    )
    parser.add_argument(
        "--ultimate-json", "-u",
        type=str,
        default=DEFAULT_ULTIMATE_JSON,
        help=f"Path to the ultimate master JSON to update (default: {DEFAULT_ULTIMATE_JSON})",
    )

    args = parser.parse_args()

    # --- Mode 1: Custom inline text ---
    if args.text:
        import hashlib
        custom_id = f"text_{hashlib.md5(args.text.strip().encode('utf-8')).hexdigest()[:6]}"
        item = {"id": custom_id, "text_prompt": args.text.strip()}
        run_text_baseline_for_prompt(item=item, model_name=args.model, ultimate_json_path=args.ultimate_json)
        return

    # --- Mode 2: From JSON file ---
    source_path = Path(args.ultimate_json) if args.from_ultimate else Path(args.from_json)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if not source_path.exists():
        print(f"Error: JSON file not found at {source_path}", file=sys.stderr)
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Error: Expected a JSON array in {source_path}", file=sys.stderr)
        sys.exit(1)

    if args.all:
        print(f"\nStarting text baseline for ALL {len(data)} prompts from: {source_path}")
        for item in data:
            try:
                run_text_baseline_for_prompt(item=item, model_name=args.model, ultimate_json_path=args.ultimate_json)
            except Exception as e:
                print(f"Error processing prompt '{item.get('id')}': {e}", file=sys.stderr)
        print(f"\nDone! Results saved to: {args.ultimate_json}")

    elif args.id:
        target_item = next((i for i in data if i.get("id") == args.id), None)
        if not target_item:
            print(f"Error: ID '{args.id}' not found in {source_path}", file=sys.stderr)
            sys.exit(1)
        run_text_baseline_for_prompt(item=target_item, model_name=args.model, ultimate_json_path=args.ultimate_json)

    else:
        target_item = data[0]
        print(f"No --id or --all specified. Defaulting to first prompt: [{target_item.get('id')}]")
        run_text_baseline_for_prompt(item=target_item, model_name=args.model, ultimate_json_path=args.ultimate_json)


if __name__ == "__main__":
    main()
