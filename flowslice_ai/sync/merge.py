"""Политика слияния полученных метаданных с конфигурацией моделей.

Правила подчинены одному принципу: автоматическая синхронизация не должна
затирать осознанный выбор пользователя. Ручные значения (``*_source ==
"manual"``) и пользовательские модели (``source == "user"``) неприкосновенны,
а поля ``temperature``/``max_tokens``/``reasoning`` синхронизация не трогает
вообще.
"""
from __future__ import annotations

from typing import Any

from flowslice_ai.sync.base import FetchedModel


def _new_model(model: FetchedModel) -> dict[str, Any]:
    """Собирает словарь новой модели, пришедшей от провайдера."""
    entry: dict[str, Any] = {
        "name": model.name or model.id,
        "builtin": False,
        "source": "provider",
        "temperature": None,
        "max_tokens": None,
        "reasoning": None,
    }
    if model.vision is not None:
        entry["vision"] = bool(model.vision)
        entry["vision_source"] = "provider"
    if model.price_in is not None or model.price_out is not None:
        if model.price_in is not None:
            entry["price_in"] = model.price_in
        if model.price_out is not None:
            entry["price_out"] = model.price_out
        entry["price_source"] = "provider"
    return entry


def _update_existing(mdef: dict[str, Any], model: FetchedModel) -> bool:
    """Обновляет существующую модель и возвращает True, если что-то изменилось."""
    changed = False
    # Имя обновляем, только если оно не задано вручную и провайдер его сообщил.
    if mdef.get("name_source") != "manual" and model.name is not None:
        if mdef.get("name") != model.name:
            mdef["name"] = model.name
            mdef["name_source"] = "provider"
            changed = True
    # Зрение: только если оно ещё неизвестно и не выставлено вручную.
    if (
        mdef.get("vision") is None
        and mdef.get("vision_source") != "manual"
        and model.vision is not None
    ):
        mdef["vision"] = bool(model.vision)
        mdef["vision_source"] = "provider"
        changed = True
    # Цены: не трогаем ручные, отсутствующие у источника значения оставляем.
    if mdef.get("price_source") != "manual":
        price_changed = False
        if model.price_in is not None and mdef.get("price_in") != model.price_in:
            mdef["price_in"] = model.price_in
            price_changed = True
        if model.price_out is not None and mdef.get("price_out") != model.price_out:
            mdef["price_out"] = model.price_out
            price_changed = True
        if price_changed:
            mdef["price_source"] = "provider"
            changed = True
    # temperature, max_tokens, reasoning и builtin не меняются сознательно.
    return changed


def update_model(mdef: dict[str, Any], model: FetchedModel) -> bool:
    """Обновляет одну модель метаданными источника.

    Публичная обёртка над :func:`_update_existing` для точечного обновления
    модели (например, сразу после её ручного добавления). Возвращает True,
    если в словаре модели что-то реально изменилось.
    """
    return _update_existing(mdef, model)


def apply_models(
    provider_models: dict[str, dict[str, Any]],
    fetched: list[FetchedModel],
    full: bool,
    allow_add: bool = True,
) -> tuple[int, int]:
    """Применяет полученные модели к словарю моделей провайдера.

    Args:
        provider_models: изменяемый словарь ``{id: mdef}`` провайдера.
        fetched: модели, полученные от источников.
        full: True — кнопка «Обновить» (обрабатываются все модели), False —
            автоматическая синхронизация (модели ``source == "user"``
            пропускаются).
        allow_add: разрешено ли дописывать в конфиг модели, которых там ещё
            нет. Для синхронизации из UI — False: полный список провайдера и
            так показывается в выборе моделей, а конфиг не раздувается на
            сотни записей. True оставлено для явного импорта в будущем.

    Returns:
        Пара (добавлено, обновлено).
    """
    added = 0
    updated = 0
    for model in fetched:
        if not model.id:
            continue
        existing = provider_models.get(model.id)
        if not isinstance(existing, dict):
            if allow_add:
                provider_models[model.id] = _new_model(model)
                added += 1
            continue
        # Хозяин барин: модель, созданную пользователем, автосинк не трогает.
        if str(existing.get("source") or "builtin") == "user" and not full:
            continue
        if _update_existing(existing, model):
            updated += 1
    return added, updated
