"""Тесты подготовки каталога хранения плагина (flowslice_ai/paths.py)."""
from __future__ import annotations

import pathlib

import pytest

from flowslice_ai.paths import (
    _find_data_dir,
    _prepare_storage_dir,
    atomic_write_text,
)


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


def test_atomic_write_text_replaces_file(tmp_path: pathlib.Path) -> None:
    """atomic_write_text() перезаписывает файл и не оставляет временный."""
    target = tmp_path / "chats.json"
    target.write_text("старое", encoding="utf-8")
    atomic_write_text(target, "новое")
    assert target.read_text(encoding="utf-8") == "новое"
    assert not (tmp_path / "chats.json.tmp").exists()


def test_atomic_write_text_keeps_old_on_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """При сбое записи старый файл остаётся нетронутым, временный удаляется."""
    target = tmp_path / "chats.json"
    target.write_text("старое", encoding="utf-8")

    def fail_replace(_src: object, _dst: object) -> None:
        raise OSError("диск недоступен")

    monkeypatch.setattr("flowslice_ai.paths.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write_text(target, "новое")
    assert target.read_text(encoding="utf-8") == "старое"
    assert not (tmp_path / "chats.json.tmp").exists()
