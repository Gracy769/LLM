"""
LLM wrapper — NVIDIA / MiniMax M2.7 via OpenAI-compatible API.
Handles: retries, logging, streaming aggregation, error classification.
"""

import time, logging
from openai import OpenAI

logger = logging.getLogger("ai-compiler")

NVIDIA_API_KEY = "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"
BASE_URL       = "https://integrate.api.nvidia.com/v1"
MODEL          = "minimaxai/minimax-m2.7"
MAX_TOKENS     = 8192
MAX_RETRIES    = 3
RETRY_DELAY    = 2  # seconds

_client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)


def call_claude(
    messages: list[dict],
    system: str = "",
    temperature: float = 0.1,
    max_tokens: int = MAX_TOKENS
) -> str:
    """
    Call MiniMax M2.7 via NVIDIA endpoint.
    Injects system prompt as first message if provided.
    Streams response and returns full aggregated text.
    Retries on transient failures.
    """
    # Build message list — system prompt prepended as a system-role message
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0 = time.time()

            completion = _client.chat.completions.create(
                model       = MODEL,
                messages    = full_messages,
                temperature = max(temperature, 0.01),  # MiniMax minimum > 0
                top_p       = 0.95,
                max_tokens  = max_tokens,
                stream      = True
            )

            # Aggregate streamed chunks into a single string
            output = []
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta.content is not None:
                    output.append(delta.content)

            text    = "".join(output)
            latency = round(time.time() - t0, 2)
            logger.info(f"LLM OK | attempt={attempt} latency={latency}s chars={len(text)}")

            if not text.strip():
                raise ValueError("Empty response from model")

            return text

        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(f"LLM failed after {MAX_RETRIES} attempts. Last error: {last_error}")
