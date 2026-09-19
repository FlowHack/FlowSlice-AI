"""Система синхронизации метаданных моделей провайдеров FlowSlice AI.

Пакет объединяет расширяемые источники сведений о моделях (список, зрение,
цены), их оркестрацию и политику слияния с конфигурацией плагина.
"""
from flowslice_ai.sync import base
from flowslice_ai.sync.base import (
    FetchedModel,
    MetadataSource,
    SourceContext,
    SourceResult,
    http_json,
)
from flowslice_ai.sync.fetch import fetch_provider_metadata
from flowslice_ai.sync.merge import apply_models
from flowslice_ai.sync.sources import SOURCES, sources_for

__all__ = [
    "FetchedModel",
    "MetadataSource",
    "SOURCES",
    "SourceContext",
    "SourceResult",
    "apply_models",
    "base",
    "fetch_provider_metadata",
    "http_json",
    "sources_for",
]
