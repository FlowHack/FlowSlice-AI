"""Генератор словаря меток настроек OrcaSlicer.

Источники:
- ``src/libslic3r/PrintConfig.cpp`` из исходников OrcaSlicer — там рядом с
  каждым id настройки лежит ``def->label = L("...")`` (английская метка);
- ``resources/i18n/<lang>/OrcaSlicer.mo`` из установленного OrcaSlicer —
  переводы этих меток (msgid — английская метка).

Результат: Python-модуль ``flowslice_ai/setting_labels_data.py`` со словарём
``LABELS[lang][setting_id] = "метка"``. Файл коммитится в репозиторий, поэтому
сборка wheel не зависит от локальной установки OrcaSlicer.

Пример запуска (пути Windows из WSL):
    python3 tools/gen_setting_labels.py \
        --source /tmp/PrintConfig.cpp \
        --i18n "/mnt/c/Program Files/OrcaSlicer/resources/i18n" \
        --version 2.5.0-dev

Скачать исходник нужной версии:
    curl -sL -o /tmp/PrintConfig.cpp \
      https://raw.githubusercontent.com/SoftFever/OrcaSlicer/main/src/libslic3r/PrintConfig.cpp
"""

from __future__ import annotations

import argparse
import gettext
import re
from datetime import date
from pathlib import Path

# Языки, для которых генерируются метки. Остальные в рантайме получат
# английский фолбэк (в OrcaSlicer нет сербской локали).
LANGS = ("en", "ru")

# Блок одной настройки: `this->add("id", coType); ... def->label = ...`.
_ADD_RE = re.compile(
    r'this->add\(\s*"([a-z0-9_]+)"\s*,[^;]*?;(.*?)(?=this->add\(|\Z)', re.S
)
# Метка может быть как L("..."), так и простым литералом ("...") / ("..."). Пустые
# литералы (->label = "") пропускаются, иначе подтягивается заголовок .mo-каталога.
_LABEL_RE = re.compile(r'->label\s*=\s*(?:L\()?\s*"((?:[^"\\]|\\.)+)"')


def _unescape(value: str) -> str:
    """Разворачивает простое C-экранирование строкового литерала."""
    replacements = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}
    return re.sub(r"\\(.)", lambda m: replacements.get(m.group(1), m.group(1)), value)


def parse_source(source: str) -> dict[str, str]:
    """Извлекает соответствие id -> английская метка из PrintConfig.cpp."""
    result: dict[str, str] = {}
    for match in _ADD_RE.finditer(source):
        key = match.group(1)
        label = _LABEL_RE.search(match.group(2))
        if label:
            result[key] = _unescape(label.group(1))
    return result


def load_catalog(i18n_dir: Path, lang: str) -> dict[str, str]:
    """Читает gettext-каталог языка; для en возвращает пустой словарь."""
    if lang == "en":
        return {}
    mo_path = i18n_dir / lang / "OrcaSlicer.mo"
    if not mo_path.is_file():
        raise SystemExit(f"Не найден каталог переводов: {mo_path}")
    with mo_path.open("rb") as handle:
        catalog = dict(gettext.GNUTranslations(handle)._catalog)  # noqa: SLF001
    # Пустой msgid — служебный заголовок .po, в словаре меток не нужен.
    catalog.pop("", None)
    return catalog


def _py_str(value: str) -> str:
    """Строковый литерал Python, безопасный для записи в модуль."""
    return repr(value)


def build_module(labels: dict[str, dict[str, str]], version: str) -> str:
    """Собирает текст Python-модуля с готовым словарём меток."""
    lines = [
        '"""Автогенерированные метки настроек OrcaSlicer.',
        "",
        "Не редактировать вручную. Пересобрать:",
        "    python3 tools/gen_setting_labels.py --source <PrintConfig.cpp> \\",
        '        --i18n "<OrcaSlicer>/resources/i18n" --version <версия>',
        "",
        f"Версия OrcaSlicer: {version}",
        f"Дата генерации: {date.today().isoformat()}",
        '"""',
        "",
        "# pylint: disable=too-many-lines,line-too-long",
        "",
        "# LABELS[язык][id настройки] = метка в интерфейсе OrcaSlicer.",
        "LABELS: dict[str, dict[str, str]] = {",
    ]
    for lang in LANGS:
        lines.append(f'    "{lang}": {{')
        for key in sorted(labels.get(lang, {})):
            lines.append(f"        {_py_str(key)}: {_py_str(labels[lang][key])},")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="путь к PrintConfig.cpp")
    parser.add_argument("--i18n", required=True, help="каталог resources/i18n")
    parser.add_argument("--version", required=True, help="версия OrcaSlicer")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "flowslice_ai" / "setting_labels_data.py"),
        help="путь к генерируемому модулю",
    )
    args = parser.parse_args()

    source = Path(args.source).read_text(encoding="utf-8", errors="replace")
    english = parse_source(source)
    if not english:
        raise SystemExit("Не удалось разобрать ни одной настройки — проверьте исходник")

    labels: dict[str, dict[str, str]] = {"en": dict(english)}
    for lang in LANGS:
        if lang == "en":
            continue
        catalog = load_catalog(Path(args.i18n), lang)
        labels[lang] = {key: catalog.get(value, value) for key, value in english.items()}

    out_path = Path(args.out)
    out_path.write_text(build_module(labels, args.version), encoding="utf-8")
    translated = sum(1 for key, val in labels["ru"].items() if val != english[key])
    print(f"Настроек: {len(english)}; русских переводов: {translated}; записан {out_path}")


if __name__ == "__main__":
    main()
