"""Пути хранения данных плагина (data_dir() — разрешённая зона аудита)."""
import logging
import os
import pathlib

_LOGGER = logging.getLogger("flowslice_ai")


def atomic_write_text(path: pathlib.Path, text: str, encoding: str = "utf-8") -> None:
    """Атомарно записывает текст: временный файл рядом + os.replace.

    Гарантирует, что при сбое (нехватка места, обрыв) не останется
    повреждённый файл: читатель увидит либо старое, либо новое содержимое.
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)
    except OSError:
        # Убираем временный файл, чтобы не мусорить в каталоге данных.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _find_data_dir() -> pathlib.Path | None:
    """data_dir() — родитель папки orca_plugins, в которой живёт плагин."""
    for parent in pathlib.Path(__file__).resolve().parents:
        if parent.name == "orca_plugins":
            return parent.parent
    return None


def _prepare_storage_dir(raw_dir: pathlib.Path, fallback_dir: pathlib.Path) -> pathlib.Path:
    """Создаёт каталог хранения, откатываясь к fallback при ошибке доступа."""
    for candidate in (raw_dir, fallback_dir):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError as exc:
            _LOGGER.error(
                "Не удалось создать каталог хранения %s: %s", candidate, exc, exc_info=True
            )
    return fallback_dir


_DATA_DIR = _find_data_dir()
_FALLBACK_DIR = pathlib.Path(__file__).resolve().parent.parent
if _DATA_DIR is not None:
    STORAGE_DIR = _prepare_storage_dir(_DATA_DIR / "flowslice_ai", _FALLBACK_DIR)
else:
    # Режим разработки: пакет лежит рядом с репозиторием.
    STORAGE_DIR = _FALLBACK_DIR

CHATS_FILE = STORAGE_DIR / "chats.json"
ICON_FILE = STORAGE_DIR / "tab_icon.svg"
