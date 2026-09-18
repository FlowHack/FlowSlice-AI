"""Конфигурация плагина: значения по умолчанию, ключи настроек и команды."""
import json
from typing import Any

from flowslice_ai.providers_data import DEFAULT_PROVIDERS

DEFAULT_CONFIG: dict[str, Any] = {
    "providers": json.loads(json.dumps(DEFAULT_PROVIDERS)),
    "active_provider": "deepseek",
    "active_model": "deepseek-chat",
    "default_model": "deepseek::deepseek-chat",
    "notes": "",
    "theme": "auto",
    "font_size": 14,
    "font_style": "system",
    "language": "en",
    "context": {},
    "temperature": 0.7,
    "max_tokens": 4096,
    "reasoning": False,
    "usage": {},
}

# Ключи настроек, отправляемые в UI (без секретов).
SETTINGS_KEYS: tuple[str, ...] = (
    "active_provider",
    "active_model",
    "default_model",
    "notes",
    "temperature",
    "max_tokens",
    "reasoning",
    "theme",
    "font_size",
    "font_style",
    "language",
)

# Служебные команды чата: единый источник для /help и state.
COMMANDS: list[tuple[str, str]] = [
    ("/context", "полный дамп контекста слайсера"),
    ("/clear", "очистить историю чата"),
    ("/model", "отчёт о модели на столе"),
    ("/printer", "сводка профилей печати"),
    ("/stats", "статистика использования"),
    ("/help", "список команд"),
    ("/reset", "сбросить настройки плагина"),
]

# Ключи, сбрасываемые кнопкой «Сбросить» на каждой вкладке настроек.
# Вкладки «Модели» и «Персональные модели» своей кнопки сброса не имеют —
# для них на вкладке «Общие значения» есть отдельные кнопки сброса коллекций.
RESET_SCOPES: dict[str, tuple[str, ...]] = {
    "general": ("notes", "temperature", "max_tokens", "reasoning"),
    "appearance": ("theme", "font_size", "font_style", "language"),
}
