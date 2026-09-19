"""Локализованные метки настроек OrcaSlicer для контекста модели.

Модель получает данные пресетов, записанные внутренними ключами OrcaSlicer
(``brim_type``, ``print_flow_ratio`` и т. п.). Чтобы в ответе она называла
параметры так, как они подписаны в интерфейсе, ключи обогащаются метками из
автогенерированного словаря: ``"Тип каймы (brim_type)"``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flowslice_ai.setting_labels_data import LABELS

# Язык-фолбэк: сербской локали в OrcaSlicer нет, поэтому для неё берём английскую.
_FALLBACK_LANG = "en"


def labels_for(lang: str) -> dict[str, str]:
    """Возвращает словарь меток языка; для неизвестного языка — английский."""
    table = LABELS.get(lang)
    return table if table else LABELS[_FALLBACK_LANG]


def param_name(lang: str, key: str) -> str | None:
    """Возвращает метку параметра в интерфейсе или None, если её нет."""
    return labels_for(lang).get(key)


def humanize_params(params: Mapping[str, Any], lang: str) -> dict[str, Any]:
    """Переименовывает ключи параметров в "Метка (id)" на языке ответа.

    Параметры без известной метки остаются под своим внутренним ключом.
    """
    table = labels_for(lang)
    result: dict[str, Any] = {}
    for key, value in params.items():
        name = table.get(key)
        result[f"{name} ({key})" if name else key] = value
    return result


def humanize_presets(presets: Mapping[str, Any], lang: str) -> dict[str, Any]:
    """Применяет humanize_params ко всем разделам данных пресетов.

    Исходный словарь не изменяется: контекст кэшируется и переиспользуется.
    """
    result: dict[str, Any] = {}
    for section, data in presets.items():
        if not isinstance(data, dict):
            result[section] = data
            continue
        section_copy: dict[str, Any] = dict(data)
        params = data.get("params")
        if isinstance(params, dict):
            section_copy["params"] = humanize_params(params, lang)
        result[section] = section_copy
    return result
