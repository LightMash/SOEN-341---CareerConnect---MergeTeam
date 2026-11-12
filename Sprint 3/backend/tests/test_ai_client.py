"""
Unit tests for services/ai_client.py

Gemini is NEVER called here. Each test swaps the real client for a small
fake that returns (or raises) exactly what that test needs. That makes the
tests free, fast, repeatable and runnable in CI without an API key.
"""

from types import SimpleNamespace

import pytest
from google.genai import errors
from pydantic import BaseModel

from services import ai_client
from services.ai_client import AIServiceError, generate_json, generate_json_with_model


class Greeting(BaseModel):
    """A tiny schema standing in for the real resume-feedback schema."""

    message: str
    language: str


# -----------------------------------------------------------------------------
# A fake Gemini client
# -----------------------------------------------------------------------------
class FakeModels:
    """
    Mimics client.models: records the call, then answers or raises.
    `error` fails every model; `errors_by_model` fails only the named ones.
    """

    def __init__(self, text=None, error=None, errors_by_model=None):
        self.text = text
        self.error = error
        self.errors_by_model = errors_by_model or {}
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if kwargs["model"] in self.errors_by_model:
            raise self.errors_by_model[kwargs["model"]]
        return SimpleNamespace(text=self.text)


@pytest.fixture(autouse=True)
def default_models(monkeypatch):
    """Every test starts with the default main and fallback models."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)


@pytest.fixture
def fake_gemini(monkeypatch):
    """
    Returns a function that installs a fake client:
        models = fake_gemini(text='{"message": "hi", "language": "en"}')
        models = fake_gemini(error=SomeError())
    `models.calls` then shows what generate_json() sent.
    """

    def _install(text=None, error=None, errors_by_model=None) -> FakeModels:
        models = FakeModels(text=text, error=error, errors_by_model=errors_by_model)
        monkeypatch.setattr(ai_client, "_get_client", lambda: SimpleNamespace(models=models))
        return models

    return _install


def gemini_error(cls, code, status):
    return cls(code, {"error": {"code": code, "message": "fake", "status": status}})


# -----------------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------------
def test_returns_parsed_pydantic_object(fake_gemini):
    fake_gemini(text='{"message": "Bonjour", "language": "fr"}')

    result = generate_json("say hi", Greeting)

    assert isinstance(result, Greeting)
    assert result.message == "Bonjour"
    assert result.language == "fr"


def test_sends_prompt_schema_and_instructions(fake_gemini, monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    models = fake_gemini(text='{"message": "hi", "language": "en"}')

    generate_json("say hi", Greeting, system_instruction="Be brief.")

    call = models.calls[0]
    assert call["model"] == ai_client.DEFAULT_MODEL
    assert call["contents"] == "say hi"
    assert call["config"].system_instruction == "Be brief."
    assert call["config"].response_mime_type == "application/json"
    # The schema Gemini receives is generated from the Pydantic model.
    assert call["config"].response_json_schema == Greeting.model_json_schema()
    assert call["config"].thinking_config.thinking_level == ai_client.THINKING_LEVEL


def test_model_can_be_overridden_with_env_var(fake_gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "some-other-model")
    models = fake_gemini(text='{"message": "hi", "language": "en"}')

    generate_json("say hi", Greeting)

    assert models.calls[0]["model"] == "some-other-model"


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
def test_missing_api_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ai_client._get_client.cache_clear()  # forget any client built by another test

    with pytest.raises(AIServiceError, match="isn't set up"):
        generate_json("say hi", Greeting)


def test_client_is_built_once_and_reused(monkeypatch):
    # Building the client makes no network call, so a fake key is fine here.
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    ai_client._get_client.cache_clear()

    first = ai_client._get_client()
    second = ai_client._get_client()

    assert first is second
    ai_client._get_client.cache_clear()  # don't leak the fake-key client into other tests


def test_client_retries_overloads_but_not_quota_or_timeouts(monkeypatch):
    built = {}
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr(ai_client.genai, "Client", lambda **kwargs: built.update(kwargs) or object())
    ai_client._get_client.cache_clear()

    ai_client._get_client()

    retry = built["http_options"].retry_options
    assert retry.attempts == 4
    assert 503 in retry.http_status_codes
    assert 429 not in retry.http_status_codes
    assert 504 not in retry.http_status_codes
    ai_client._get_client.cache_clear()


# -----------------------------------------------------------------------------
# Errors from Gemini become friendly AIServiceErrors
# -----------------------------------------------------------------------------
def test_rate_limit_asks_user_to_retry(fake_gemini):
    fake_gemini(error=gemini_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED"))

    with pytest.raises(AIServiceError, match="busy"):
        generate_json("say hi", Greeting)


def test_other_client_error(fake_gemini):
    fake_gemini(error=gemini_error(errors.ClientError, 400, "INVALID_ARGUMENT"))

    with pytest.raises(AIServiceError, match="couldn't process"):
        generate_json("say hi", Greeting)


def test_server_error(fake_gemini):
    fake_gemini(error=gemini_error(errors.ServerError, 503, "UNAVAILABLE"))

    with pytest.raises(AIServiceError, match="unavailable"):
        generate_json("say hi", Greeting)


def test_gemini_timeout(fake_gemini):
    fake_gemini(error=gemini_error(errors.ServerError, 504, "DEADLINE_EXCEEDED"))

    with pytest.raises(AIServiceError, match="took too long"):
        generate_json("say hi", Greeting)


def test_network_failure(fake_gemini):
    fake_gemini(error=TimeoutError("timed out"))

    with pytest.raises(AIServiceError, match="Couldn't reach"):
        generate_json("say hi", Greeting)


def test_error_message_does_not_leak_internal_details(fake_gemini):
    fake_gemini(error=RuntimeError("secret internal detail: key=abc123"))

    with pytest.raises(AIServiceError) as caught:
        generate_json("say hi", Greeting)

    assert "abc123" not in str(caught.value)


# -----------------------------------------------------------------------------
# Bad answers from Gemini
# -----------------------------------------------------------------------------
def test_empty_answer(fake_gemini):
    fake_gemini(text=None)  # what Gemini gives when a safety filter blocks it

    with pytest.raises(AIServiceError, match="didn't return"):
        generate_json("say hi", Greeting)


def test_answer_that_is_not_json(fake_gemini):
    fake_gemini(text="Sure! Here is your greeting: hello")

    with pytest.raises(AIServiceError, match="unexpected"):
        generate_json("say hi", Greeting)


def test_json_with_wrong_shape(fake_gemini):
    fake_gemini(text='{"message": "hi"}')  # "language" is missing

    with pytest.raises(AIServiceError, match="unexpected"):
        generate_json("say hi", Greeting)


# -----------------------------------------------------------------------------
# Fallback model when the main one is overloaded
# -----------------------------------------------------------------------------
GOOD_ANSWER = '{"message": "hi", "language": "en"}'
MAIN = ai_client.DEFAULT_MODEL
FALLBACK = ai_client.DEFAULT_FALLBACK_MODEL


def test_overloaded_main_model_falls_back(fake_gemini):
    models = fake_gemini(
        text=GOOD_ANSWER,
        errors_by_model={MAIN: gemini_error(errors.ServerError, 503, "UNAVAILABLE")},
    )

    result, used = generate_json_with_model("say hi", Greeting)

    assert result.message == "hi"
    assert used == FALLBACK
    assert [call["model"] for call in models.calls] == [MAIN, FALLBACK]


def test_main_model_is_reported_when_it_answers(fake_gemini):
    fake_gemini(text=GOOD_ANSWER)

    _, used = generate_json_with_model("say hi", Greeting)

    assert used == MAIN


def test_both_models_overloaded(fake_gemini):
    models = fake_gemini(error=gemini_error(errors.ServerError, 503, "UNAVAILABLE"))

    with pytest.raises(AIServiceError, match="unavailable"):
        generate_json("say hi", Greeting)

    assert len(models.calls) == 2


@pytest.mark.parametrize(
    "error",
    [
        gemini_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED"),  # quota: retrying wastes more
        gemini_error(errors.ClientError, 400, "INVALID_ARGUMENT"),  # our request is wrong
        gemini_error(errors.ServerError, 504, "DEADLINE_EXCEEDED"),  # already waited long
    ],
)
def test_other_errors_do_not_use_the_fallback(fake_gemini, error):
    models = fake_gemini(text=GOOD_ANSWER, errors_by_model={MAIN: error})

    with pytest.raises(AIServiceError):
        generate_json("say hi", Greeting)

    assert len(models.calls) == 1


def test_fallback_can_be_turned_off(fake_gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    models = fake_gemini(
        text=GOOD_ANSWER,
        errors_by_model={MAIN: gemini_error(errors.ServerError, 503, "UNAVAILABLE")},
    )

    with pytest.raises(AIServiceError, match="unavailable"):
        generate_json("say hi", Greeting)

    assert len(models.calls) == 1


def test_no_fallback_when_it_is_the_same_model(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", MAIN)

    assert ai_client.models_to_try() == [MAIN]
