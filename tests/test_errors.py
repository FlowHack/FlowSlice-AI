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


def test_message_preserved() -> None:
    """Текст ошибки сохраняется как есть для показа пользователю."""
    error = ApiError("Сервер вернул 429")
    assert str(error) == "Сервер вернул 429"
    assert isinstance(error, FlowSliceError)


def test_specific_errors_are_independent() -> None:
    """Специализированные ошибки не наследуют друг друга."""
    assert not issubclass(ApiError, NetworkError)
    assert not issubclass(NetworkError, ApiError)
    assert not issubclass(ConfigError, ApiError)
    assert not issubclass(StreamError, NetworkError)
