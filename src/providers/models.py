# src/providers/models.py

from typing import Dict, Any

MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "local_qwen": {
        "id": "local_qwen",
        "provider": "local_qwen",
        "name": "Foundry Local Qwen",
        "is_free": True,
        "is_local": True,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.0,
        "output_cost_per_m": 0.0,
        "context_limit": 8192
    },
    "groq/llama3-8b-8192": {
        "id": "groq/llama3-8b-8192",
        "provider": "groq",
        "name": "Llama 3 8B (Groq)",
        "is_free": True,  # Groq has a free tier usually
        "is_local": False,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.05,
        "output_cost_per_m": 0.08,
        "context_limit": 8192
    },
    "groq/llama3-70b-8192": {
        "id": "groq/llama3-70b-8192",
        "provider": "groq",
        "name": "Llama 3 70B (Groq)",
        "is_free": False,
        "is_local": False,
        "tags": ["smart", "economic"],
        "input_cost_per_m": 0.59,
        "output_cost_per_m": 0.79,
        "context_limit": 8192
    },
    "gemini/gemini-1.5-flash": {
        "id": "gemini/gemini-1.5-flash",
        "provider": "gemini",
        "name": "Gemini 1.5 Flash",
        "is_free": True, # Has a generous free tier for developers
        "is_local": False,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.35,
        "output_cost_per_m": 1.05,
        "context_limit": 1000000
    },
    "gemini/gemini-1.5-pro": {
        "id": "gemini/gemini-1.5-pro",
        "provider": "gemini",
        "name": "Gemini 1.5 Pro",
        "is_free": False,
        "is_local": False,
        "tags": ["smart"],
        "input_cost_per_m": 3.50,
        "output_cost_per_m": 10.50,
        "context_limit": 1000000
    },
    "openai/gpt-3.5-turbo": {
        "id": "openai/gpt-3.5-turbo",
        "provider": "openai",
        "name": "GPT-3.5 Turbo",
        "is_free": False,
        "is_local": False,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.50,
        "output_cost_per_m": 1.50,
        "context_limit": 16384
    },
    "openai/gpt-4o": {
        "id": "openai/gpt-4o",
        "provider": "openai",
        "name": "GPT-4o",
        "is_free": False,
        "is_local": False,
        "tags": ["smart"],
        "input_cost_per_m": 5.00,
        "output_cost_per_m": 15.00,
        "context_limit": 128000
    },
    "openai/gpt-4o-mini": {
        "id": "openai/gpt-4o-mini",
        "provider": "openai",
        "name": "GPT-4o Mini",
        "is_free": False,
        "is_local": False,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.15,
        "output_cost_per_m": 0.60,
        "context_limit": 128000
    },
    "anthropic/claude-3-haiku-20240307": {
        "id": "anthropic/claude-3-haiku-20240307",
        "provider": "anthropic",
        "name": "Claude 3 Haiku",
        "is_free": False,
        "is_local": False,
        "tags": ["fast", "economic"],
        "input_cost_per_m": 0.25,
        "output_cost_per_m": 1.25,
        "context_limit": 200000
    },
    "anthropic/claude-3-5-sonnet-20240620": {
        "id": "anthropic/claude-3-5-sonnet-20240620",
        "provider": "anthropic",
        "name": "Claude 3.5 Sonnet",
        "is_free": False,
        "is_local": False,
        "tags": ["smart"],
        "input_cost_per_m": 3.00,
        "output_cost_per_m": 15.00,
        "context_limit": 200000
    },
    "openrouter/auto": {
        "id": "openrouter/auto",
        "provider": "openrouter",
        "name": "OpenRouter Auto",
        "is_free": False,
        "is_local": False,
        "tags": ["smart"],
        "input_cost_per_m": 5.00,
        "output_cost_per_m": 15.00,
        "context_limit": 8192
    },
    "mistral/mistral-large-latest": {
        "id": "mistral/mistral-large-latest",
        "provider": "mistral",
        "name": "Mistral Large",
        "is_free": False,
        "is_local": False,
        "tags": ["smart"],
        "input_cost_per_m": 2.00,
        "output_cost_per_m": 6.00,
        "context_limit": 32000
    }
}
