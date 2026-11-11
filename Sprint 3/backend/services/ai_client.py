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

This file knows nothing about resumes. The resume prompt and the shape of
the feedback live in the feedback service

Configuration (backend/.env):
  GEMINI_API_KEY=...            required, from Google AI Studio
  GEMINI_MODEL=gemini-3.8-flash optional, overrides DEFAULT_MODEL
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
DEFAULT_MODEL = "gemini-3.8-flash"

# Give up after this long rather than leaving the user's request hanging.
TIMEOUT_SECONDS = 60

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
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set; AI features are disabled.")
        raise AIServiceError("AI feedback isn't set up on this server yet.")

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),  # in milliseconds
    )


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def generate_json(prompt: str, schema: type[T], system_instruction: str | None = None) -> T:
    """
    Sends `prompt` to Gemini and returns its answer as an instance of `schema`.

    `schema` is a Pydantic model. Its JSON Schema is sent to Gemini, which is
    then constrained to answer with JSON of exactly that shape. We still
    validate the answer with Pydantic, because Gemini ignores some schema
    rules (e.g. string lengths) and a model can always misbehave.

    `system_instruction` holds the standing rules (role, tone, what not to
    do), kept separate from `prompt`, which holds the data for this request.

    Raises AIServiceError on any failure.
    """
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=TEMPERATURE,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
    except errors.ClientError as exc:  # 4xx: our request or our account
        logger.warning("Gemini rejected the request: %s", exc)
        if exc.code == 429:
            raise AIServiceError(
                "The AI service is busy right now. Please try again in a minute."
            ) from exc
        raise AIServiceError("The AI service couldn't process this request.") from exc
    except errors.APIError as exc:  # 5xx and anything else from Gemini
        logger.error("Gemini API error: %s", exc)
        raise AIServiceError("The AI service is unavailable right now. Please try again later.") from exc
    except Exception as exc:  # network down, timeout, DNS...
        logger.error("Could not reach Gemini: %s", exc)
        raise AIServiceError("Couldn't reach the AI service. Please try again later.") from exc

    # .text is None when Gemini returns no answer at all (e.g. it was
    # blocked by a safety filter).
    if not response.text:
        logger.warning("Gemini returned an empty response: %r", response)
        raise AIServiceError("The AI didn't return any feedback. Please try again.")

    try:
        return schema.model_validate_json(response.text)
    except ValidationError as exc:
        logger.error("Gemini answer didn't match %s: %s", schema.__name__, exc)
        raise AIServiceError("The AI returned an unexpected answer. Please try again.") from exc


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

    result = generate_json("Say hello to a new CareerConnect user, in French.", _Greeting)
    print(f"Model: {_model_name()}")
    print(f"Parsed: {result!r}")
