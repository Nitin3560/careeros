import os
import time

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

load_dotenv()

MATCHING_MODEL = "deepseek-ai/deepseek-v4-flash"

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    timeout=60.0,
)


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    for attempt in range(3):
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
        except APIStatusError as exc:
            if exc.status_code not in {429, 500, 502, 503, 504, 529} or attempt == 2:
                raise
            time.sleep(2**attempt)

    raise RuntimeError("LLM request failed")
