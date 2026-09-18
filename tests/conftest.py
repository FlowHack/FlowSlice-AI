"""Общие фикстуры pytest для пакета FlowSlice AI."""
from __future__ import annotations

import pathlib
import sys

import pytest

# Корень репозитория (пакет flowslice_ai) и мок-модуль orca
# подключаются ДО импорта flowslice_ai.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MOCKS = pathlib.Path(__file__).parent / "mocks"
if str(_MOCKS) not in sys.path:
    sys.path.insert(0, str(_MOCKS))


@pytest.fixture
def engine(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Создаёт _ChatEngine с временным хранилищем чатов."""
    from flowslice_ai.engine import _ChatEngine

    monkeypatch.setattr("flowslice_ai.engine.core.CHATS_FILE", tmp_path / "chats.json")

    class _FakeCap:
        """Заглушка capability с конфигурацией."""

        def __init__(self) -> None:
            self._config = "{}"

        def get_config(self) -> str:
            """Возвращает конфигурацию."""
            return self._config

        def save_config(self, config: str) -> bool:
            """Сохраняет конфигурацию."""
            self._config = str(config)
            return True

    return _ChatEngine(_FakeCap())