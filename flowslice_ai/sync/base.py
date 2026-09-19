"""Базовые типы системы синхронизации метаданных моделей.

Пакет ``flowslice_ai.sync`` описывает расширяемые источники сведений о
моделях провайдеров (список моделей, поддержка изображений, цены) и
политику слияния этих сведений с конфигурацией плагина.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from flowslice_ai.constants import HTTP_HEADERS
from flowslice_ai.logging import _LOGGER

# Сетевые ошибки, которые источник обязан перехватить и вернуть текстом.
_NET_ERRORS = (urllib.error.URLError, TimeoutError, ValueError, OSError)


@dataclass(frozen=True)
class FetchedModel:
    """Сведение об одной модели, полученное из внешнего источника.

    Цены указаны в USD за 1M токенов. ``vision`` — поддержка изображений
    (True/False) либо None, если источник её не сообщает.
    """

    id: str
    name: str | None = None
    vision: bool | None = None
    price_in: float | None = None
    price_out: float | None = None


@dataclass
class SourceResult:
    """Результат работы одного источника метаданных."""

    models: list[FetchedModel] = field(default_factory=list)
    vision: dict[str, bool] = field(default_factory=dict)
    prices: dict[str, tuple[float, float]] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class SourceContext:
    """Контекст опроса источников для конкретного провайдера."""

    provider_id: str
    base_url: str
    api_key: str
    scheme: str
    timeout: int = 10


def http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 10) -> Any:
    """Возвращает распарсенный JSON по URL.

    Единая точка выхода в сеть для всех источников: её подменяют в тестах.
    На не-2xx поднимает :class:`urllib.error.HTTPError`, на сетевую ошибку —
    ``URLError``/``TimeoutError``, на битый JSON — ``ValueError``.
    """
    request = urllib.request.Request(url, headers=headers or dict(HTTP_HEADERS))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", "replace")
    return json.loads(raw)


class MetadataSource:
    """Базовый источник метаданных моделей (не абстрактный).

    Наследники задают ``id``, набор ``attributes`` из ``{"models", "vision",
    "pricing"}``, приоритет (меньше — раньше) и реализуют ``_fetch``.
    Метод :meth:`fetch` сам перехватывает сетевые и разборные ошибки,
    возвращая их в ``SourceResult.error``, и наружу их не бросает.
    """

    id: str = ""
    attributes: frozenset[str] = frozenset()
    priority: int = 0
    requires_key: bool = True

    def matches(self, _ctx: SourceContext) -> bool:
        """Возвращает True, если источник применим к данному провайдеру."""
        return False

    def _fetch(self, _ctx: SourceContext) -> SourceResult:
        """Реализация конкретного источника: без перехвата ошибок."""
        return SourceResult()

    def fetch(self, ctx: SourceContext) -> SourceResult:
        """Опрашивает источник и никогда не бросает сетевые ошибки наружу."""
        try:
            return self._fetch(ctx)
        except _NET_ERRORS as exc:
            _LOGGER.warning(
                "Источник %s не смог получить данные провайдера %s: %s",
                self.id,
                ctx.provider_id,
                exc,
            )
            return SourceResult(error=str(exc))
