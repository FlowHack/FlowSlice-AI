"""Конфигурация плагина: значения по умолчанию, ключи настроек и команды."""
import json
from typing import Any

from flowslice_ai.constants import (
    DEFAULT_MAX_ATTACHMENT_MB,
    DEFAULT_IMAGE_MAX_SIDE,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MAX_TOKENS,
    MAX_IMAGES_IN_HISTORY,
)
from flowslice_ai.providers_data import DEFAULT_PROVIDERS

# Версия схемы конфигурации: увеличивается при несовместимых миграциях.
CONFIG_VERSION = 2

DEFAULT_CONFIG: dict[str, Any] = {
    "providers": json.loads(json.dumps(DEFAULT_PROVIDERS)),
    "active_provider": "deepseek",
    "active_model": "deepseek-chat",
    "default_model": "deepseek::deepseek-chat",
    "favorites": [],
    "notes": "",
    "theme": "auto",
    "font_size": 14,
    "font_style": "system",
    "language": "en",
    "context": {},
    "temperature": 0.3,
    "max_tokens": DEFAULT_MAX_TOKENS,
    "reasoning": False,
    "compact_enabled": True,
    "auto_sync_providers": True,
    "compact_threshold": 80,
    "context_window": 128000,
    "max_history_images": MAX_IMAGES_IN_HISTORY,
    "image_max_side": DEFAULT_IMAGE_MAX_SIDE,
    "image_quality": DEFAULT_IMAGE_QUALITY,
    "max_attachment_mb": DEFAULT_MAX_ATTACHMENT_MB,
    "usage": {},
}

# Ключи настроек, отправляемые в UI (без секретов).
SETTINGS_KEYS: tuple[str, ...] = (
    "active_provider",
    "active_model",
    "default_model",
    "favorites",
    "notes",
    "temperature",
    "max_tokens",
    "reasoning",
    "compact_enabled",
    "auto_sync_providers",
    "compact_threshold",
    "context_window",
    "max_history_images",
    "image_max_side",
    "image_quality",
    "max_attachment_mb",
    "theme",
    "font_size",
    "font_style",
    "language",
)

# Служебные команды чата: единый источник для /help и state.
COMMANDS: list[tuple[str, str]] = [
    ("/context", "полный дамп контекста слайсера"),
    ("/compact", "сжать историю чата в короткую сводку"),
    ("/clear", "очистить историю чата"),
    ("/model", "отчёт о модели на столе"),
    ("/printer", "сводка профилей печати"),
    ("/stats", "статистика использования"),
    ("/help", "список команд"),
    ("/reset", "сбросить настройки плагина (/reset chats — очистить чаты)"),
]

# Ключи, сбрасываемые кнопкой «Сбросить» на каждой вкладке настроек.
# Вкладки «Модели» и «Персональные модели» своей кнопки сброса не имеют —
# для них на вкладке «Общие значения» есть отдельные кнопки сброса коллекций.
RESET_SCOPES: dict[str, tuple[str, ...]] = {
    "general": (
        "notes",
        "temperature",
        "max_tokens",
        "reasoning",
        "compact_enabled",
        "compact_threshold",
        "context_window",
        "max_history_images",
        "image_max_side",
        "image_quality",
        "max_attachment_mb",
    ),
    "appearance": ("theme", "font_size", "font_style", "language"),
}


def normalize_temperature(value: Any) -> float | None:
    """Приводит temperature к float в диапазоне 0..2, иначе None."""
    if value is None:
        return None
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return None
    if temperature < 0.0 or temperature > 2.0:
        return None
    return temperature


def normalize_max_tokens(value: Any) -> int | None:
    """Приводит max_tokens к int в диапазоне 1..100000, иначе None."""
    if value is None:
        return None
    try:
        max_tokens = int(value)
    except (TypeError, ValueError):
        return None
    if max_tokens < 1 or max_tokens > 100000:
        return None
    return max_tokens
