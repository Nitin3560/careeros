import os
import threading
import time
from collections import deque

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ALL_PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": "gemini-3.5-flash-lite",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY"),
        "model": "llama-3.3-70b-versatile",
    },
}

PROVIDER_TPM_BUDGET = {
    "gemini": 200_000,
    "groq": 10_000,
}
PROVIDER_RPM_BUDGET = {
    "gemini": 12,
    "groq": 25,
}


class RateLimiter:
    def __init__(self):
        provider_names = set(PROVIDER_TPM_BUDGET) | set(PROVIDER_RPM_BUDGET)
        self._tokens = {name: deque() for name in provider_names}
        self._requests = {name: deque() for name in provider_names}
        self._lock = threading.Lock()

    def _prune(self, provider_name: str, now: float):
        token_window = self._tokens[provider_name]
        while token_window and token_window[0][0] < now - 60:
            token_window.popleft()

        request_window = self._requests[provider_name]
        while request_window and request_window[0] < now - 60:
            request_window.popleft()

    def wait_if_needed(self, provider_name: str, estimated_tokens: int):
        token_budget = PROVIDER_TPM_BUDGET.get(provider_name)
        request_budget = PROVIDER_RPM_BUDGET.get(provider_name)
        if token_budget is None and request_budget is None:
            return

        while True:
            with self._lock:
                now = time.time()
                self._prune(provider_name, now)
                current_tokens = sum(tokens for _, tokens in self._tokens[provider_name])
                current_requests = len(self._requests[provider_name])

                token_ok = (
                    token_budget is None
                    or current_tokens + estimated_tokens <= token_budget
                )
                request_ok = (
                    request_budget is None
                    or current_requests + 1 <= request_budget
                )

                if token_ok and request_ok:
                    self._tokens[provider_name].append((now, estimated_tokens))
                    self._requests[provider_name].append(now)
                    return

                wait_candidates = []
                if not token_ok:
                    wait_candidates.append(60 - (now - self._tokens[provider_name][0][0]))
                if not request_ok:
                    wait_candidates.append(60 - (now - self._requests[provider_name][0]))
                wait_time = max(0.5, min(wait_candidates))

            print(
                f"[ai_client] {provider_name} would exceed local rate budget, "
                f"waiting {wait_time:.1f}s..."
            )
            time.sleep(min(wait_time, 5))


_rate_limiter = RateLimiter()


def estimate_tokens(system_prompt: str, user_prompt: str, max_tokens: int) -> int:
    input_tokens = (len(system_prompt) + len(user_prompt)) // 4
    return input_tokens + max_tokens


def call_llm(
    system_prompt: str,
    user_prompt: str,
    provider_order: list[str],
    max_tokens: int = 800,
    max_retries: int = 2,
) -> str:
    last_error = None
    estimated_tokens = estimate_tokens(system_prompt, user_prompt, max_tokens)

    for provider_name in provider_order:
        provider = ALL_PROVIDERS.get(provider_name)
        if not provider:
            continue
        if not provider["api_key"]:
            continue

        client = OpenAI(
            base_url=provider["base_url"],
            api_key=provider["api_key"],
            timeout=30.0,
        )

        for attempt in range(max_retries):
            try:
                _rate_limiter.wait_if_needed(provider_name, estimated_tokens)
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
                    f"[ai_client] {provider_name} attempt {attempt + 1} "
                    f"failed: {exc}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        print(f"[ai_client] {provider_name} exhausted, trying next provider.")

    raise last_error
