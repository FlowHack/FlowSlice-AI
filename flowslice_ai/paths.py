"""Пути хранения данных плагина (data_dir() — разрешённая зона аудита)."""
import logging
import pathlib

_LOGGER = logging.getLogger("flowslice_ai")


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
