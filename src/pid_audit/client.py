"""
client.py - OpenRouter client shared across all modules.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI


def get_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENROUTER_API_KEY. Set it in your environment or .env file."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

TEXT_MODEL = "google/gemini-3-flash-preview"
VISION_MODEL = "google/gemini-3-flash-preview"
