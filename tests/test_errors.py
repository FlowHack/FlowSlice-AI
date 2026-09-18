"""Тесты иерархии классов ошибок пакета FlowSlice AI."""
from __future__ import annotations

from flowslice_ai.errors import (
    ApiError,
    ConfigError,
    ContextError,
    FlowSliceError,
    NetworkError,
    StreamError,
)


def test_hierarchy() -> None:
    """Все специализированные ошибки наследуют FlowSliceError, тот — Exception."""
    assert issubclass(FlowSliceError, Exception)
    for error_cls in (ConfigError, ApiError, NetworkError, StreamError, ContextError):
        assert issubclass(error_cls, FlowSliceError)