"""Тесты патча метаданных wheel под Orca Slicer (tools/patch_wheel.py)."""
from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path

import pytest

from tools.patch_wheel import (
    IMPORT_NAME,
    ORCA_CLOUD_TARGET_SUFFIX,
    _record_row,
    make_orca_cloud_copy,
    patch_wheel,
)

_META = "flowslice_ai-0.1.0.dist-info/METADATA"
_RECORD = "flowslice_ai-0.1.0.dist-info/RECORD"


def _make_wheel(path: Path, metadata: str = "Metadata-Version: 2.1\nName: FlowSlice-AI\nVersion: 0.1.0\n") -> None:
    """Создаёт минимальный wheel с METADATA и RECORD."""
    meta_bytes = metadata.encode("utf-8")
    record = _record_row(_META, meta_bytes) + "\n" + f"{_RECORD},,\n"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(_META, meta_bytes)
        archive.writestr(_RECORD, record)


def _read(path: Path, name: str) -> str:
    """Читает текстовый файл из wheel."""
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def test_patch_wheel_sets_display_and_import_name(tmp_path: Path) -> None:
    """Патч ставит Name с пробелом и Import-Name, не ломая RECORD."""
    wheel = tmp_path / "flowslice_ai-0.1.0-py3-none-any.whl"
    _make_wheel(wheel)

    patch_wheel(wheel)

    metadata = _read(wheel, _META)
    assert "Name: FlowSlice AI" in metadata
    assert f"Import-Name: {IMPORT_NAME}" in metadata

    record = _read(wheel, _RECORD)
    row = next(line for line in record.splitlines() if line.startswith(_META))
    digest = base64.urlsafe_b64encode(
        hashlib.sha256(metadata.encode("utf-8")).digest()
    ).rstrip(b"=")
    assert f"sha256={digest.decode('ascii')}" in row
    assert row.endswith(f",{len(metadata.encode('utf-8'))}")


def test_patch_wheel_is_idempotent(tmp_path: Path) -> None:
    """Повторный патч не дублирует Import-Name."""
    wheel = tmp_path / "flowslice_ai-0.1.0-py3-none-any.whl"
    _make_wheel(wheel)

    patch_wheel(wheel)
    patch_wheel(wheel)

    metadata = _read(wheel, _META)
    assert metadata.count("Import-Name:") == 1


def test_make_orca_cloud_copy_adds_target_suffix(tmp_path: Path) -> None:
    """Копия для OrcaCloud получает суффикс цели ``_any`` и совпадает байт-в-байт."""
    wheel = tmp_path / "flowslice_ai-0.1.0-py3-none-any.whl"
    _make_wheel(wheel)

    patched = make_orca_cloud_copy(wheel)

    assert patched is not None
    assert patched.name == f"flowslice_ai-0.1.0-py3-none-any{ORCA_CLOUD_TARGET_SUFFIX}.whl"
    assert patched.read_bytes() == wheel.read_bytes()
    assert make_orca_cloud_copy(patched) is None


def test_patch_wheel_requires_metadata(tmp_path: Path) -> None:
    """wheel без METADATA отвергается с понятной ошибкой."""
    wheel = tmp_path / "broken-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("flowslice_ai/__init__.py", "")
    with pytest.raises(SystemExit):
        patch_wheel(wheel)
