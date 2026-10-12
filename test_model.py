import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import langchain_google_genai.chat_models

_original_chat_with_retry = langchain_google_genai.chat_models._chat_with_retry
def _patched_chat_with_retry(*args, **kwargs):
    kwargs.pop("max_retries", None)
    kwargs.pop("timeout", None)
    return _original_chat_with_retry(*args, **kwargs)
langchain_google_genai.chat_models._chat_with_retry = _patched_chat_with_retry

load_dotenv()

target_model = ChatGoogleGenerativeAI(
    model="gemma-4-31b-it",
    temperature=0.7
)

try:
    res = target_model.invoke("Hello")
    print(res.content)
except Exception as e:
    print(f"Error: {e}")
