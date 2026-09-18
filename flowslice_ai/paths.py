"""Пути хранения данных плагина (data_dir() — разрешённая зона аудита)."""
import pathlib


def _find_data_dir() -> pathlib.Path | None:
    """data_dir() — родитель папки orca_plugins, в которой живёт плагин."""
    for parent in pathlib.Path(__file__).resolve().parents:
        if parent.name == "orca_plugins":
            return parent.parent
    return None


_DATA_DIR = _find_data_dir()
if _DATA_DIR is not None:
    STORAGE_DIR = _DATA_DIR / "flowslice_ai"
else:
    # Режим разработки: пакет лежит рядом с репозиторием.
    STORAGE_DIR = pathlib.Path(__file__).resolve().parent.parent

try:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    STORAGE_DIR = pathlib.Path(__file__).resolve().parent.parent
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CHATS_FILE = STORAGE_DIR / "chats.json"
ICON_FILE = STORAGE_DIR / "tab_icon.svg"
