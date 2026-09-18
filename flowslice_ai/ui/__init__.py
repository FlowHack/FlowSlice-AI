"""Сборка HTML-страниц интерфейса из ресурсов пакета."""
# pylint: disable=duplicate-code

from importlib import resources

_UI = resources.files("flowslice_ai.ui")


def _read(name: str) -> str:
    """Читает ресурс пакета как текст."""
    return _UI.joinpath(name).read_text(encoding="utf-8")


HTML_PAGE = (
    _read("index.html")
    .replace("<!--STYLE-->", _read("style.css"))
    .replace("<!--SCRIPT-->", _read("app.js"))
)

CONFIG_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="<!--LANG-->">
<head>
<meta charset="utf-8">
<title>FlowSlice AI</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; color: var(--orca-fg, #222); background: var(--orca-bg, #fff); }
  h1 { font-size: 18px; margin: 0 0 8px; }
  p { font-size: 13px; line-height: 1.5; color: var(--orca-muted, #666); max-width: 560px; }
  code { background: var(--orca-input, #f0f0f0); padding: 1px 5px; border-radius: 4px; }
</style>
</head>
<body>
  <h1>FlowSlice AI</h1>
  <p><!--P1--></p>
  <p><!--P2--></p>
</body>
</html>
"""

# Тексты страницы настроек плагина для языков интерфейса.
_CONFIG_TEXTS: dict[str, tuple[str, str]] = {
    "en": (
        "All plugin settings are managed from the \u00abSettings\u00bb (gear) button on the "
        "FlowSlice AI tab: providers, models, API keys, temperature, context notes and appearance.",
        "This page intentionally has no fields: settings are stored in the plugin configuration "
        "and edited only on the tab.",
    ),
    "ru": (
        "Все настройки плагина управляются через кнопку \u00abНастройки\u00bb (шестерёнка) на вкладке "
        "FlowSlice AI: провайдеры, модели, API-ключи, температура, заметки для контекста и оформление.",
        "Эта страница намеренно не содержит полей — настройки хранятся в конфигурации плагина "
        "и редактируются только на вкладке.",
    ),
    "sr": (
        "Sva pode\u0161avanja dodatka ure\u0111uju se preko dugmeta \u00abPode\u0161avanja\u00bb (zup\u010danik) na "
        "kartici FlowSlice AI: provajderi, modeli, API klju\u010devi, temperatura, bele\u0161ke i izgled.",
        "Ova stranica namerno nema polja: pode\u0161avanja se \u010duvaju u konfiguraciji dodatka "
        "i menjaju se samo na kartici.",
    ),
}


def config_page(lang: str = "en") -> str:
    """Собирает страницу настроек плагина на указанном языке интерфейса."""
    if lang not in _CONFIG_TEXTS:
        lang = "en"
    first, second = _CONFIG_TEXTS[lang]
    return (
        CONFIG_PAGE_TEMPLATE.replace("<!--LANG-->", lang)
        .replace("<!--P1-->", first)
        .replace("<!--P2-->", second)
    )


CONFIG_PAGE = config_page("en")
