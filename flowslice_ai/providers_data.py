"""Встроенные провайдеры ИИ и их модели по умолчанию."""
from typing import Any

DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "deepseek-chat": {
                "name": "DeepSeek V4 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "deepseek-reasoner": {
                "name": "DeepSeek V4 Pro",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "openrouter/auto": {
                "name": "Auto",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "openrouter/auto-beta": {
                "name": "Auto (beta)",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "openrouter/free": {
                "name": "Free",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "deepseek/deepseek-chat-v3-0324": {
                "name": "DeepSeek V3 (0324)",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "anthropic/claude-sonnet-4-5": {
                "name": "Claude Sonnet 4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "openai/gpt-5.1": {
                "name": "GPT-5.1",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "google/gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "meta-llama/llama-3.3-70b-instruct:free": {
                "name": "Llama 3.3 70B (free)",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "gemini-2.5-flash": {
                "name": "Gemini 2.5 Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gemini-2.5-pro": {
                "name": "Gemini 2.5 Pro",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gemini-2.5-flash-lite": {
                "name": "Gemini 2.5 Flash Lite",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "anthropic",
        "models": {
            "claude-opus-4-8": {
                "name": "Claude Opus 4.8",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "claude-sonnet-4-6": {
                "name": "Claude Sonnet 4.6",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "claude-haiku-4-5": {
                "name": "Claude Haiku 4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "gpt-5.1": {
                "name": "GPT-5.1",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gpt-5-mini": {
                "name": "GPT-5 Mini",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "gpt-4o": {
                "name": "GPT-4o",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "llama-3.3-70b-versatile": {
                "name": "Llama 3.3 70B Versatile",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "llama-3.1-8b-instant": {
                "name": "Llama 3.1 8B Instant",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "deepseek-r1-distill-llama-70b": {
                "name": "DeepSeek R1 Distill 70B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "glm": {
        "name": "Zhipu GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "glm-4.6": {
                "name": "GLM-4.6",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "glm-4.5": {
                "name": "GLM-4.5",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "glm-4-flash": {
                "name": "GLM-4-Flash",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "llama3.3-70b": {
                "name": "Llama 3.3 70B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "llama-3.1-8b": {
                "name": "Llama 3.1 8B",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "mistral": {
        "name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "mistral-large-latest": {
                "name": "Mistral Large",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "mistral-small-latest": {
                "name": "Mistral Small",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
    "xai": {
        "name": "xAI",
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "builtin": True,
        "scheme": "openai",
        "models": {
            "grok-3": {
                "name": "Grok 3",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
            "grok-3-mini": {
                "name": "Grok 3 Mini",
                "builtin": True,
                "temperature": None,
                "max_tokens": None,
                "reasoning": None,
            },
        },
    },
}

# Поддержка изображений по умолчанию: True — модель принимает изображения,
# False — не принимает, None — неизвестно (тогда уходят обе подсказки).
# Ключ — (id провайдера, id модели); "*" задаёт значение для всех моделей.
_VISION_BY_MODEL: dict[tuple[str, str], bool | None] = {
    ("deepseek", "*"): False,
    ("openrouter", "*"): None,
    ("google", "*"): True,
    ("anthropic", "*"): True,
    ("openai", "*"): True,
    ("groq", "*"): False,
    ("glm", "*"): None,
    ("cerebras", "*"): False,
    ("mistral", "*"): True,
    ("xai", "*"): None,
}


def _apply_vision_defaults() -> None:
    """Проставляет каждой встроенной модели поле vision и его источник.

    ``vision_source`` принимает значения: ``default`` — из этого каталога,
    ``provider`` — получено запросом к API провайдера, ``manual`` — задано
    пользователем в настройках.
    """
    for provider_id, provider in DEFAULT_PROVIDERS.items():
        default_vision = _VISION_BY_MODEL.get((provider_id, "*"))
        for model_id, model in provider["models"].items():
            if (provider_id, model_id) in _VISION_BY_MODEL:
                model["vision"] = _VISION_BY_MODEL[(provider_id, model_id)]
            else:
                model["vision"] = default_vision
            model["vision_source"] = "default"


_apply_vision_defaults()
