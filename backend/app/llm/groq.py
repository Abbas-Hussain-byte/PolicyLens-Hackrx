"""Groq LLM client with rate limiting, JSON extraction, and Gemini fallback.

Uses httpx to connect to Groq's OpenAI-compatible API endpoints.
"""

import httpx
import json
import re
import asyncio
import time
import logging
from app.config import settings
from app.llm import gemini

logger = logging.getLogger(__name__)

# Rate limiter state
_last_call_time: float = 0.0
_call_count_this_minute: int = 0
_minute_start: float = 0.0


async def _rate_limit():
    """Simple rate limiter for Groq free tier (typically 30 RPM)."""
    global _last_call_time, _call_count_this_minute, _minute_start

    now = time.time()
    # Reset counter each minute
    if now - _minute_start > 60:
        _call_count_this_minute = 0
        _minute_start = now

    # If we've hit the limit, wait
    limit = settings.groq_rpm or 30
    if _call_count_this_minute >= limit - 1:  # Leave 1 buffer
        wait_time = 60 - (now - _minute_start) + 1
        if wait_time > 0:
            logger.warning(f"Groq Rate limit approaching, waiting {wait_time:.1f}s")
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
    temperature: float = None,
    max_tokens: int = 2048,
    json_mode: bool = True,
) -> str:
    """Generate text using Groq with fallback to Gemini.

    Args:
        prompt: The prompt text.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        json_mode: Whether to request JSON output.

    Returns:
        Generated text string.
    """
    temp = temperature if temperature is not None else settings.temperature
    if not settings.groq_api_key:
        logger.info("GROQ_API_KEY not set. Falling back to Gemini.")
        return await gemini.generate(prompt, temp, max_tokens, json_mode)

    await _rate_limit()

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temp,
        "top_p": settings.top_p,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                logger.error(f"Groq API error (status {response.status_code}): {response.text}")
                # Fallback to Gemini if Groq encounters a server error or rate limits
                logger.warning("Groq API error. Falling back to Gemini.")
                return await gemini.generate(prompt, temp, max_tokens, json_mode)

            result_json = response.json()
            choices = result_json.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                return choices[0]["message"]["content"].strip()
            else:
                logger.error(f"Empty response from Groq: {result_json}")
                return "{}" if json_mode else ""

    except Exception as e:
        logger.error(f"Groq API call exception: {e}. Falling back to Gemini.")
        try:
            return await gemini.generate(prompt, temp, max_tokens, json_mode)
        except Exception as gemini_err:
            logger.error(f"Gemini fallback failed: {gemini_err}")
            raise e


async def generate_json(
    prompt: str,
    temperature: float = None,
    max_tokens: int = 2048,
) -> dict:
    """Generate and parse JSON response from Groq with fallback to Gemini.

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
    if not settings.groq_api_key:
        return await gemini.classify(prompt)

    await _rate_limit()

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 50,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                logger.error(f"Groq classify error (status {response.status_code}): {response.text}")
                return await gemini.classify(prompt)

            result_json = response.json()
            choices = result_json.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                return choices[0]["message"]["content"].strip()
            return ""
    except Exception as e:
        logger.error(f"Groq classify exception: {e}. Falling back to Gemini.")
        return await gemini.classify(prompt)


async def check_connection() -> bool:
    """Check if Groq API is accessible. Fallback to Gemini if Groq not set."""
    if not settings.groq_api_key:
        return await gemini.check_connection()

    try:
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.groq_model,
            "messages": [{"role": "user", "content": "Reply with just: ok"}],
            "max_tokens": 10,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            return response.status_code == 200
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

    logger.warning(f"Failed to parse JSON from Groq response: {text[:200]}")
    return {"error": "Failed to parse response", "raw": text[:500]}
