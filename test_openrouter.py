import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import requests

load_dotenv()

headers = {
  "Authorization": f"Bearer {os.environ.get('OPENROUTER_KEY')}"
}

response = requests.get("https://openrouter.ai/api/v1/models", headers=headers)
models = response.json().get("data", [])

gemma_models = [m["id"] for m in models if "gemma" in m["id"].lower()]
print("Gemma models on OpenRouter:", gemma_models)
