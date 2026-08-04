import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MATCHING_MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    timeout=30.0,
)


def call_llm(
    system_prompt: str, user_prompt: str, max_tokens: int = 800, max_retries: int = 3
) -> str:
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MATCHING_MODEL,
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
                f"[ai_client] Attempt {attempt + 1} failed: {exc}. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    raise last_error
