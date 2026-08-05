import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROVIDERS = [
    {
        "name": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": "gemini-3.5-flash-lite",
    },
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY"),
        "model": "llama-3.3-70b-versatile",
    },
]


def call_llm(
    system_prompt: str, user_prompt: str, max_tokens: int = 800, max_retries: int = 2
) -> str:
    last_error = None

    for provider in PROVIDERS:
        if not provider["api_key"]:
            continue

        client = OpenAI(
            base_url=provider["base_url"],
            api_key=provider["api_key"],
            timeout=30.0,
        )

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=provider["model"],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
                return response.choices[0].message.content
            except Exception as exc:
                last_error = exc
                wait_time = 2**attempt
                print(
                    f"[ai_client] {provider['name']} attempt {attempt + 1} "
                    f"failed: {exc}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        print(f"[ai_client] {provider['name']} exhausted retries.")

    raise last_error
