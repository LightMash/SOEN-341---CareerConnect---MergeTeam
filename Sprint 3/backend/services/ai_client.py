"""
Owner: AI Resume Feedback
The ONLY file in the backend that talks to Google Gemini.

Everything else asks for AI output through `generate_json()`. Keeping the
provider behind this one function means:
  - tests replace one function instead of faking HTTP calls (see
    tests/test_ai_client.py), so CI never needs an API key or internet;
  - switching provider or model later only changes this file;
  - every Gemini error is turned into one AIServiceError with a message
    that is safe to show users (the real error is logged for us).

Configuration (backend/.env):
  GEMINI_API_KEY=...            required, from Google AI Studio
  GEMINI_MODEL=...              optional, overrides DEFAULT_MODEL
  GEMINI_FALLBACK_MODEL=...     optional, overrides DEFAULT_FALLBACK_MODEL ("" = off)
"""

import logging
import os
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# A fast, cheap model that is on Gemini's free tier. Model names change
# often, so it can be overridden with GEMINI_MODEL without a code change.
# Flash-Lite rather than Flash: during testing gemini-3.8-flash was often
# overloaded on the free tier (503 / timeouts), and Lite is plenty for
# reviewing a resume.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Second model, tried only when the first one is still overloaded (500/503)
# after the retries below. Each model has its own capacity on Google's side,
# so this rescues most "high demand" failures (about 8% of requests failed
# without it during testing). Must be a Gemini 3+ model, because of
# THINKING_LEVEL. Override with GEMINI_FALLBACK_MODEL in .env, or set
# GEMINI_FALLBACK_MODEL= (empty) to turn the fallback off.
DEFAULT_FALLBACK_MODEL = "gemini-3.1-flash-lite"

# Give up after this long rather than leaving the user's request hanging.
# The SDK also sends it to Google as the server-side deadline, so a value
# that's too short makes Gemini itself answer 504 DEADLINE_EXCEEDED.
TIMEOUT_SECONDS = 120

# Gemini 3 models "think" before answering. Reviewing a resume doesn't need
# deep reasoning, and LOW is much faster (our first real request timed out
# at the default level). Only Gemini 3+ models accept this setting.
THINKING_LEVEL = types.ThinkingLevel.LOW

# When Gemini is overloaded (503 "high demand", common on the free tier) or
# has an internal error (500), the SDK waits a moment and tries again by
# itself: 1 try + 3 retries, about 2s, 4s, then 8s apart. Not retried on purpose:
# 429 (our quota is used up, retrying only wastes more) and 504 (each try can
# already take TIMEOUT_SECONDS).
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=4,
    initial_delay=2.0,
    max_delay=10.0,
    http_status_codes=[500, 503],
)

# Low temperature = more consistent, less "creative" answers. For feedback
# we want the same resume to get similar suggestions each time.
TEMPERATURE = 0.3

# "Any Pydantic model": lets generate_json() return the exact type it was
# given, so callers get autocompletion on the result.
T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    """Raised for every AI failure. The message is safe to show the user."""


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """
    Builds the Gemini client the first time it's needed, then reuses it.

    Importing this module (which the app does at startup,
    and pytest does in CI) must work even when no API key is set. Only an
    actual AI request needs one. lru_cache doesn't cache exceptions, so if
    the key is added later the next call will succeed.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set; AI features are disabled.")
        raise AIServiceError("AI feedback isn't set up on this server yet.")

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_SECONDS * 1000,  # in milliseconds
            retry_options=RETRY_OPTIONS,
        ),
    )


def model_name() -> str:
    """The Gemini model in use (GEMINI_MODEL from .env, or DEFAULT_MODEL)."""
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def models_to_try() -> list[str]:
    """The main model, then the fallback (if one is set and it's different)."""
    primary = model_name()
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    if fallback and fallback != primary:
        return [primary, fallback]
    return [primary]


def _ask(client: genai.Client, model: str, prompt: str, schema: type[BaseModel], system_instruction: str | None):
    """One request to one model. Lets the SDK's own errors through."""
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=TEMPERATURE,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
        ),
    )


def _friendly_error(exc: Exception) -> AIServiceError:
    """Logs the real error for us and returns a message that's safe for users."""
    if isinstance(exc, errors.ClientError):  # 4xx: our request or our account
        logger.warning("Gemini rejected the request: %s", exc)
        if exc.code == 429:
            return AIServiceError("The AI service is busy right now. Please try again in a minute.")
        return AIServiceError("The AI service couldn't process this request.")
    if isinstance(exc, errors.APIError):  # 5xx and anything else from Gemini
        if exc.code == 504:  # Gemini gave up: DEADLINE_EXCEEDED
            logger.error("Gemini timed out: %s", exc)
            return AIServiceError("The AI took too long to answer. Please try again.")
        logger.error("Gemini API error: %s", exc)
        return AIServiceError("The AI service is unavailable right now. Please try again later.")
    logger.error("Could not reach Gemini: %s", exc)  # network down, timeout, DNS...
    return AIServiceError("Couldn't reach the AI service. Please try again later.")


def generate_json_with_model(
    prompt: str, schema: type[T], system_instruction: str | None = None
) -> tuple[T, str]:
    """
    Sends `prompt` to Gemini and returns (answer, name of the model that answered).

    `schema` is a Pydantic model. Its JSON Schema is sent to Gemini, which is
    then constrained to answer with JSON of exactly that shape. We still
    validate the answer with Pydantic, because Gemini ignores some schema
    rules (e.g. string lengths) and a model can always misbehave.

    `system_instruction` holds the standing rules (role, tone, what not to
    do), kept separate from `prompt`, which holds the data for this request.

    If the main model is overloaded (500/503, after the SDK's own retries),
    the same request goes to the fallback model. Other errors are NOT
    passed on to the fallback: a 429 means our quota is used up, a 4xx means
    the request itself is wrong, and a 504 already waited TIMEOUT_SECONDS.

    Raises AIServiceError on any failure.
    """
    client = _get_client()
    models = models_to_try()

    for index, model in enumerate(models):
        try:
            response = _ask(client, model, prompt, schema, system_instruction)
            break
        except errors.APIError as exc:
            has_next = index + 1 < len(models)
            if exc.code in (500, 503) and has_next:
                logger.warning("%s is overloaded (%s); trying %s", model, exc.code, models[index + 1])
                continue
            raise _friendly_error(exc) from exc
        except Exception as exc:
            raise _friendly_error(exc) from exc

    # .text is None when Gemini returns no answer at all (e.g. it was
    # blocked by a safety filter).
    if not response.text:
        logger.warning("Gemini returned an empty response: %r", response)
        raise AIServiceError("The AI didn't return any feedback. Please try again.")

    try:
        return schema.model_validate_json(response.text), model
    except ValidationError as exc:
        logger.error("Gemini answer didn't match %s: %s", schema.__name__, exc)
        raise AIServiceError("The AI returned an unexpected answer. Please try again.") from exc


def generate_json(prompt: str, schema: type[T], system_instruction: str | None = None) -> T:
    """Same as generate_json_with_model(), for callers that don't need the model name."""
    result, _model = generate_json_with_model(prompt, schema, system_instruction)
    return result


# -----------------------------------------------------------------------------
# Manual check: does my API key work?
#   cd backend  (venv active, GEMINI_API_KEY in .env)
#   python -m services.ai_client
# Not used by the app or by tests.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    class _Greeting(BaseModel):
        message: str
        language: str

    result, used = generate_json_with_model("Say hello to a new CareerConnect user, in French.", _Greeting)
    print(f"Model: {used}")
    print(f"Parsed: {result!r}")
