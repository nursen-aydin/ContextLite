import pytest
from unittest.mock import patch, MagicMock
from src.providers.litellm_router import classify_litellm_error, ProviderError
import litellm

def test_invalid_api_key():
    err = litellm.AuthenticationError("Incorrect API key provided: sk-invalid", llm_provider="openai", model="gpt-4o")
    classified = classify_litellm_error(err)
    assert classified.category == "invalid_api_key"
    assert classified.code == "invalid_api_key"

def test_credit_balance_exhausted():
    err_message = "Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}}"
    err = litellm.RateLimitError(err_message, llm_provider="openai", model="gpt-4o")
    classified = classify_litellm_error(err)
    assert classified.category == "billing_required"
    assert classified.code == "credit_balance_exhausted"

def test_rate_limited():
    err_message = "Rate limit reached for requests"
    err = litellm.RateLimitError(err_message, llm_provider="openai", model="gpt-4o")
    classified = classify_litellm_error(err)
    assert classified.category == "rate_limited"

def test_model_not_found():
    err_message = "The model `gpt-4-unknown` does not exist"
    err = Exception(err_message)
    classified = classify_litellm_error(err)
    assert classified.category == "model_unavailable"
