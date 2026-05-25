"""Gemini LLM client with rate limiting and JSON extraction.

Uses google-genai SDK with the free tier (15 RPM).
"""

from google import genai
from google.genai import types
from app.config import settings
import json
import re
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

# Rate limiter state
_last_call_time: float = 0.0
_call_count_this_minute: int = 0
_minute_start: float = 0.0


def _get_client() -> genai.Client:
    """Get the Gemini client."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not set. Get a free key at aistudio.google.com")
    return genai.Client(api_key=settings.gemini_api_key)


async def _rate_limit():
    """Simple rate limiter for Gemini free tier (15 RPM)."""
    global _last_call_time, _call_count_this_minute, _minute_start

    now = time.time()
    # Reset counter each minute
    if now - _minute_start > 60:
        _call_count_this_minute = 0
        _minute_start = now

    # If we've hit the limit, wait
    if _call_count_this_minute >= settings.gemini_rpm - 1:  # Leave 1 buffer
        wait_time = 60 - (now - _minute_start) + 1
        if wait_time > 0:
            logger.warning(f"Rate limit approaching, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            _call_count_this_minute = 0
            _minute_start = time.time()

    # Minimum gap between calls (100ms)
    elapsed = now - _last_call_time
    if elapsed < 0.1:
        await asyncio.sleep(0.1 - elapsed)

    _call_count_this_minute += 1
    _last_call_time = time.time()


async def generate(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    json_mode: bool = True,
) -> str:
    """Generate text using Gemini.

    Args:
        prompt: The prompt text.
        temperature: Sampling temperature (lower = more focused).
        max_tokens: Maximum output tokens.
        json_mode: Whether to request JSON output.

    Returns:
        Generated text string.
    """
    await _rate_limit()

    client = _get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    if json_mode:
        config.response_mime_type = "application/json"

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config=config,
        )

        if response.text:
            return response.text.strip()
        else:
            logger.error(f"Empty response from Gemini. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}")
            return "{}" if json_mode else ""

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise


async def generate_json(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Generate and parse JSON response from Gemini.

    Args:
        prompt: The prompt text.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.

    Returns:
        Parsed JSON dictionary.
    """
    text = await generate(prompt, temperature, max_tokens, json_mode=True)
    return _parse_json(text)


async def classify(prompt: str) -> str:
    """Generate a short classification response (no JSON).

    Used for query routing where we just need a tier label.
    """
    await _rate_limit()

    client = _get_client()

    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=50,
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config=config,
        )
        return response.text.strip() if response.text else ""
    except Exception as e:
        logger.error(f"Gemini classify error: {e}")
        return ""


async def check_connection() -> bool:
    """Check if Gemini API is accessible."""
    try:
        client = _get_client()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents="Reply with just: ok",
            config=types.GenerateContentConfig(max_output_tokens=10),
        )
        return bool(response.text)
    except Exception:
        return False


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM output, handling common issues."""
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to parse JSON from Gemini response: {text[:200]}")
    return {"error": "Failed to parse response", "raw": text[:500]}
