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

CONFIG_PAGE = """<!DOCTYPE html>
<html lang="ru">
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
  <p>Все настройки плагина управляются через кнопку «Настройки» (шестерёнка) на вкладке FlowSlice AI: провайдеры, модели, API-ключи, температура, заметки для контекста и оформление.</p>
  <p>Эта страница намеренно не содержит полей — настройки хранятся в конфигурации плагина и редактируются только на вкладке.</p>
</body>
</html>
"""
