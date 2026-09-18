"""Тесты подготовки каталога хранения плагина (flowslice_ai/paths.py)."""
from __future__ import annotations

import pathlib

from flowslice_ai.paths import _find_data_dir, _prepare_storage_dir


def test_prepare_storage_dir_creates_directory(tmp_path: pathlib.Path) -> None:
    """_prepare_storage_dir() создаёт целевой каталог и возвращает его."""
    raw = tmp_path / "data" / "flowslice_ai"
    fallback = tmp_path / "fallback"
    result = _prepare_storage_dir(raw, fallback)
    assert result == raw
    assert raw.is_dir()


def test_prepare_storage_dir_falls_back_on_error(tmp_path: pathlib.Path) -> None:
    """Если целевой путь занят файлом, используется резервный каталог."""
    raw = tmp_path / "blocked"
    raw.write_text("не каталог", encoding="utf-8")
    fallback = tmp_path / "fallback"
    result = _prepare_storage_dir(raw, fallback)
    assert result == fallback
    assert fallback.is_dir()


def test_find_data_dir_returns_path_or_none() -> None:
    """_find_data_dir() возвращает существующий путь либо None вне Orca."""
    found = _find_data_dir()
    assert found is None or found.is_dir()
