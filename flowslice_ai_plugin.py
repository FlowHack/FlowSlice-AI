# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
#
# [tool.orcaslicer.plugin]
# name = "FlowSlice AI"
# description = "ИИ-ассистент инженера 3D-печати в OrcaSlicer: механика, Klipper и тонкая настройка материалов."
# author = "FlowSlice AI Team"
# version = "0.1.0"
# ///
"""FlowSlice AI — нативный Python-плагин OrcaSlicer с ИИ-ассистентом.

Монолитный плагин: вся логика, пользовательский интерфейс и стили хранятся
в одном файле. Этапы E1+E2 реализуют базовую архитектуру, слой конфигурации
и полноценную страницу настроек.
"""

import importlib
import json
import logging
import pathlib
import sys
import threading
from typing import Any

import orca

try:
    import numpy as _np
    _HAS_NUMPY = _np is not None
except ImportError:
    _np = None
    _HAS_NUMPY = False


try:
    _PAGES_BASE = getattr(
        importlib.import_module("orca.pages"), "PagesPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _PAGES_BASE = None

try:
    _SCRIPT_BASE = getattr(
        importlib.import_module("orca.script"), "ScriptPluginCapabilityBase", None
    )
except (ImportError, AttributeError):
    _SCRIPT_BASE = None


_LOGGER = logging.getLogger("flowslice_ai")
if not _LOGGER.handlers:
    _STREAM_HANDLER = logging.StreamHandler(sys.stderr)
    _STREAM_HANDLER.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    _LOGGER.addHandler(_STREAM_HANDLER)
    _LOGGER.setLevel(logging.INFO)


DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "",
    "custom_base_url": "",
    "custom_model": "",
    "theme": "auto",
    "font_size": 14,
    "font_style": "system",
    "usage": {},
}

SYSTEM_PROMPT = (
    "You are FlowSlice AI, a strictly professional 3D-printing engineer embedded "
    "in OrcaSlicer. Provide highly technical, concrete advice. Focus expertise on "
    "mechanics, Klipper firmware configuration, and precise material tuning "
    "(e.g., PETG, TPU)."
)

HTTP_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "OrcaSlicer/2.5.0",
}

TIMEOUT = 120
MAX_IMAGE_B64 = 6_000_000
MAX_FILE_CHARS = 1_000_000
MAX_CHAT_MESSAGES = 200
STREAM_THROTTLE = 0.15
MAX_IMAGES_IN_HISTORY = 2
MAX_CONTEXT_CHARS = 60_000

CONTEXT_OPTIONS = ("filament", "printer", "print", "model", "history")

STORAGE_DIR = pathlib.Path(__file__).resolve().parent
CHATS_FILE = STORAGE_DIR / "chats.json"
ICON_FILE = STORAGE_DIR / "tab_icon.svg"


class FlowSliceError(Exception):
    """Базовая ошибка плагина FlowSlice AI."""


class ConfigError(FlowSliceError):
    """Ошибка чтения, нормализации или сохранения конфигурации."""


class ApiError(FlowSliceError):
    """Ошибка ответа внешнего ИИ-провайдера."""


class NetworkError(FlowSliceError):
    """Ошибка сетевого взаимодействия."""


class StreamError(FlowSliceError):
    """Ошибка потоковой передачи ответа модели."""


class ContextError(FlowSliceError):
    """Ошибка сбора контекста слайсера."""


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>FlowSlice AI</title>
</head>
<body>
<p>FlowSlice AI</p>
</body>
</html>"""


_CONFIG_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Настройки FlowSlice AI</title>
<style>
:root {
  --accent: #d9534f;
  --accent-fg: #ffffff;
}
* {
  box-sizing: border-box;
}
html,
body {
  margin: 0;
  padding: 0;
}
body {
  padding: 16px;
  background: var(--orca-bg);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
}
h1 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
}
.subtitle {
  margin: 0 0 16px 0;
  color: var(--orca-muted);
  font-size: 12px;
}
.card {
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 12px;
}
.card-title {
  margin: 0 0 10px 0;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--orca-muted);
}
.provider {
  display: flex;
  gap: 10px;
}
.provider input[type="radio"] {
  display: none;
}
.provider label {
  flex: 1;
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  padding: 10px;
  text-align: center;
  cursor: pointer;
  user-select: none;
}
.provider input[type="radio"]:checked + label {
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent);
}
.field {
  margin-bottom: 12px;
}
.field:last-child {
  margin-bottom: 0;
}
.field label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--orca-muted);
}
input[type="text"],
input[type="password"],
select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-bg);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
}
input:focus,
select:focus {
  outline: none;
  border-color: var(--accent);
}
input[type="range"] {
  width: 100%;
  accent-color: var(--accent);
}
.row {
  display: flex;
  gap: 12px;
}
.row > .field {
  flex: 1;
}
.stats {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
.stat {
  flex: 1;
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  padding: 10px;
  text-align: center;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
}
.stat-label {
  margin-top: 4px;
  font-size: 11px;
  color: var(--orca-muted);
}
button.danger {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: transparent;
  color: var(--accent);
  font-family: var(--orca-font);
  font-size: 14px;
  cursor: pointer;
}
button.danger:hover {
  background: var(--accent);
  color: var(--accent-fg);
}
.footnote {
  margin-top: 16px;
  text-align: center;
  font-size: 11px;
  color: var(--orca-muted);
}
</style>
</head>
<body>
<h1>FlowSlice AI</h1>
<p class="subtitle">Настройки ассистента инженера 3D-печати</p>

<div class="card">
  <p class="card-title">Провайдер</p>
  <div class="provider">
    <input type="radio" id="provider-deepseek" name="provider" value="deepseek">
    <label for="provider-deepseek">DeepSeek</label>
    <input type="radio" id="provider-openrouter" name="provider" value="openrouter">
    <label for="provider-openrouter">OpenRouter</label>
    <input type="radio" id="provider-custom" name="provider" value="custom">
    <label for="provider-custom">Custom</label>
  </div>
</div>

<div class="card">
  <p class="card-title">Модель и доступ</p>
  <div class="field" id="modelSelectWrap">
    <label for="modelSelect">Модель</label>
    <select id="modelSelect"></select>
  </div>
  <div class="field" id="customModelWrap">
    <label for="customModel">Идентификатор модели</label>
    <input type="text" id="customModel" placeholder="например, deepseek-chat">
  </div>
  <div class="field" id="customBaseWrap">
    <label for="customBase">Базовый URL API</label>
    <input type="text" id="customBase" placeholder="https://api.example.com/v1">
  </div>
  <div class="field">
    <label for="apiKey">API-ключ</label>
    <input type="password" id="apiKey" autocomplete="off">
  </div>
</div>

<div class="card">
  <p class="card-title">Оформление</p>
  <div class="row">
    <div class="field">
      <label for="theme">Тема</label>
      <select id="theme">
        <option value="auto">Авто</option>
        <option value="light">Светлая</option>
        <option value="dark">Тёмная</option>
      </select>
    </div>
    <div class="field">
      <label for="fontStyle">Стиль шрифта</label>
      <select id="fontStyle">
        <option value="system">Системный</option>
        <option value="mono">Моноширинный</option>
        <option value="serif">С засечками</option>
      </select>
    </div>
  </div>
  <div class="field">
    <label for="fontSize">Размер шрифта: <span id="fontSizeValue">14</span></label>
    <input type="range" id="fontSize" min="10" max="20" step="1" value="14">
  </div>
</div>

<div class="card">
  <p class="card-title">Статистика использования</p>
  <div class="field">
    <label for="period">Период</label>
    <select id="period">
      <option value="day">День</option>
      <option value="week">Неделя</option>
      <option value="month">Месяц</option>
      <option value="all">Всё время</option>
    </select>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value" id="statMsgs">0</div>
      <div class="stat-label">Сообщения</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="statTokens">0</div>
      <div class="stat-label">Токены</div>
    </div>
  </div>
</div>

<div class="card">
  <button type="button" class="danger" id="resetBtn">Сбросить настройки</button>
</div>

<p class="footnote">FlowSlice AI v0.1.0</p>

<script>
const DEFAULTS = __DEFAULTS_JSON__;

const MODELS = {
  deepseek: [
    { value: "deepseek-chat", label: "DeepSeek V4 Flash" },
    { value: "deepseek-reasoner", label: "DeepSeek Reasoner" }
  ],
  openrouter: [
    { value: "deepseek/deepseek-v4-flash-0731", label: "DeepSeek V4 Flash (OpenRouter)" },
    { value: "openrouter/auto", label: "OpenRouter Auto" }
  ],
  custom: []
};

let cfg = {};

function byId(id) {
  return document.getElementById(id);
}

function pad2(value) {
  return (value < 10 ? "0" : "") + String(value);
}

function todayKey() {
  const now = new Date();
  return String(now.getFullYear()) + "-" + pad2(now.getMonth() + 1) + "-" + pad2(now.getDate());
}

function monthKey() {
  const now = new Date();
  return String(now.getFullYear()) + "-" + pad2(now.getMonth() + 1);
}

function parseDayKey(key) {
  const parts = String(key).split("-");
  if (parts.length !== 3) {
    return null;
  }
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  if (!year || !month || !day) {
    return null;
  }
  return new Date(year, month - 1, day);
}

function sumUsage(period) {
  const usage = cfg.usage && typeof cfg.usage === "object" ? cfg.usage : {};
  const keys = Object.keys(usage);
  const now = new Date();
  const today = todayKey();
  const currentMonth = monthKey();
  let msgs = 0;
  let tokens = 0;
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    let include = false;
    if (period === "day") {
      include = key === today;
    } else if (period === "month") {
      include = key.indexOf(currentMonth) === 0;
    } else if (period === "week") {
      const parsed = parseDayKey(key);
      if (parsed) {
        const diff = (now.getTime() - parsed.getTime()) / 86400000;
        include = diff >= 0 && diff < 7;
      }
    } else {
      include = true;
    }
    if (include) {
      const item = usage[key] || {};
      msgs += Number(item.msgs) || 0;
      tokens += Number(item.tokens) || 0;
    }
  }
  return { msgs: msgs, tokens: tokens };
}

function updateStats() {
  const result = sumUsage(byId("period").value);
  byId("statMsgs").textContent = String(result.msgs);
  byId("statTokens").textContent = String(result.tokens);
}

function renderProvider() {
  const provider = cfg.provider || DEFAULTS.provider;
  const radios = document.querySelectorAll("input[name=provider]");
  for (let i = 0; i < radios.length; i++) {
    radios[i].checked = radios[i].value === provider;
  }
  const modelSelect = byId("modelSelect");
  const options = MODELS[provider] || [];
  modelSelect.innerHTML = "";
  for (let j = 0; j < options.length; j++) {
    const option = document.createElement("option");
    option.value = options[j].value;
    option.textContent = options[j].label;
    modelSelect.appendChild(option);
  }
  const isCustom = provider === "custom";
  byId("modelSelectWrap").style.display = isCustom ? "none" : "block";
  byId("customModelWrap").style.display = isCustom ? "block" : "none";
  byId("customBaseWrap").style.display = isCustom ? "block" : "none";
  if (isCustom) {
    byId("customModel").value = cfg.custom_model || "";
  } else {
    let matched = false;
    for (let k = 0; k < options.length; k++) {
      if (options[k].value === cfg.model) {
        matched = true;
      }
    }
    if (!matched && options.length > 0) {
      cfg.model = options[0].value;
    }
    modelSelect.value = cfg.model || "";
  }
  byId("customBase").value = cfg.custom_base_url || "";
}

function fillForm() {
  renderProvider();
  byId("apiKey").value = cfg.api_key || "";
  byId("theme").value = cfg.theme || DEFAULTS.theme;
  byId("fontSize").value = String(cfg.font_size || DEFAULTS.font_size);
  byId("fontSizeValue").textContent = String(cfg.font_size || DEFAULTS.font_size);
  byId("fontStyle").value = cfg.font_style || DEFAULTS.font_style;
  updateStats();
}

function collect() {
  const provider = cfg.provider || DEFAULTS.provider;
  if (provider === "custom") {
    cfg.custom_model = byId("customModel").value.trim();
    cfg.model = cfg.custom_model;
    cfg.custom_base_url = byId("customBase").value.trim();
  } else {
    cfg.model = byId("modelSelect").value;
  }
  cfg.api_key = byId("apiKey").value;
  cfg.theme = byId("theme").value;
  cfg.font_size = parseInt(byId("fontSize").value, 10) || DEFAULTS.font_size;
  cfg.font_style = byId("fontStyle").value;
  if (!cfg.usage || typeof cfg.usage !== "object") {
    cfg.usage = {};
  }
  window.orca.saveConfig(cfg);
}

function setProvider(provider) {
  cfg.provider = provider;
  renderProvider();
  collect();
}

function resetAll() {
  cfg = JSON.parse(JSON.stringify(DEFAULTS));
  fillForm();
  window.orca.saveConfig(cfg);
}

function wire() {
  const radios = document.querySelectorAll("input[name=provider]");
  for (let i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", function () {
      setProvider(this.value);
    });
  }
  byId("modelSelect").addEventListener("change", collect);
  byId("customModel").addEventListener("input", collect);
  byId("customBase").addEventListener("input", collect);
  byId("apiKey").addEventListener("input", collect);
  byId("theme").addEventListener("change", collect);
  byId("fontStyle").addEventListener("change", collect);
  byId("fontSize").addEventListener("input", function () {
    byId("fontSizeValue").textContent = this.value;
    collect();
  });
  byId("period").addEventListener("change", updateStats);
  byId("resetBtn").addEventListener("click", resetAll);
}

document.addEventListener("DOMContentLoaded", function () {
  const stored = window.orca.getConfig();
  cfg = {};
  const defaultKeys = Object.keys(DEFAULTS);
  for (let i = 0; i < defaultKeys.length; i++) {
    cfg[defaultKeys[i]] = DEFAULTS[defaultKeys[i]];
  }
  if (stored && typeof stored === "object") {
    const storedKeys = Object.keys(stored);
    for (let j = 0; j < storedKeys.length; j++) {
      cfg[storedKeys[j]] = stored[j];
    }
  }
  fillForm();
  wire();
});
</script>
</body>
</html>"""


CONFIG_PAGE = _CONFIG_PAGE_TEMPLATE.replace(
    "__DEFAULTS_JSON__", json.dumps(DEFAULT_CONFIG)
)


class _ChatEngine:
    """Движок плагина: общая логика без наследования от capability.

    На этапе E1 хранит только слой конфигурации, на последующих этапах
    дополняется работой с сетью, контекстом и историей чатов.
    """

    def __init__(self, cap: Any) -> None:
        """Сохраняет ссылку на capability и загружает конфигурацию."""
        self._cap = cap
        self._persist_lock = threading.Lock()
        self._config = self._normalize_config(self._read_raw_config())

    def _read_raw_config(self) -> dict:
        """Читает и разбирает сырую JSON-конфигурацию capability."""
        raw = self._cap.get_config()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("Не удалось разобрать конфигурацию, используются значения по умолчанию")
            return {}
        if not isinstance(data, dict):
            _LOGGER.warning("Конфигурация не является объектом, используются значения по умолчанию")
            return {}
        return data

    def _normalize_config(self, data: dict) -> dict:
        """Приводит произвольный словарь настроек к валидной схеме."""
        merged = DEFAULT_CONFIG.copy()
        if isinstance(data, dict):
            merged.update(data)
        if merged.get("provider") not in ("deepseek", "openrouter", "custom"):
            merged["provider"] = "deepseek"
        if merged.get("theme") not in ("auto", "light", "dark"):
            merged["theme"] = "auto"
        if merged.get("font_style") not in ("system", "mono", "serif"):
            merged["font_style"] = "system"
        try:
            font_size = int(merged.get("font_size", 14))
        except (TypeError, ValueError):
            font_size = 14
        if font_size < 10 or font_size > 20:
            font_size = 14
        merged["font_size"] = font_size
        usage = merged.get("usage")
        merged["usage"] = dict(usage) if isinstance(usage, dict) else {}
        return merged

    def load_config(self) -> dict:
        """Возвращает копию текущей конфигурации."""
        return dict(self._config)

    def save_config(self, config: dict) -> bool:
        """Нормализует и сохраняет конфигурацию через capability."""
        self._config = self._normalize_config(config)
        with self._persist_lock:
            try:
                return bool(self._cap.save_config(json.dumps(self._config)))
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Не удалось сериализовать конфигурацию: %s", exc)
                return False

    def reset_config(self) -> dict:
        """Сбрасывает конфигурацию к значениям по умолчанию."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        with self._persist_lock:
            try:
                self._cap.save_config(json.dumps(self._config))
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Не удалось сохранить конфигурацию по умолчанию: %s", exc)
        return dict(self._config)


class _ConfigMixin:
    """Общие методы конфигурации для вкладки и окна плагина."""

    def get_default_config(self) -> dict:
        """Возвращает дефолтную конфигурацию плагина."""
        return DEFAULT_CONFIG.copy()

    def get_config(self) -> str:
        """Возвращает конфигурацию базового capability либо пустой JSON."""
        getter: Any = getattr(super(), "get_config", None)
        if getter is not None:
            return str(getter())
        return "{}"

    def save_config(self, config: str) -> bool:
        """Сохраняет конфигурацию через базовый capability."""
        setter: Any = getattr(super(), "save_config", None)
        if setter is not None:
            return bool(setter(config))
        return False

    def has_config_ui(self) -> bool:
        """Сообщает хосту о наличии кастомной страницы настроек."""
        return True

    def get_config_ui(self) -> str:
        """Возвращает HTML-страницу настроек."""
        return CONFIG_PAGE

    def _ensure_engine(self) -> "_ChatEngine":
        """Лениво создаёт общий движок плагина."""
        engine = getattr(self, "_engine", None)
        if engine is None:
            engine = _ChatEngine(self)
            self._engine = engine
        return engine


if _PAGES_BASE is not None:

    class FlowSliceTab(_ConfigMixin, _PAGES_BASE):
        """Вкладка FlowSlice AI в главном окне OrcaSlicer."""

        def get_name(self) -> str:
            """Имя вкладки."""
            return "FlowSlice AI"

        def get_ui(self) -> str:
            """HTML-содержимое вкладки."""
            self._ensure_engine()
            return HTML_PAGE

        def get_icon(self) -> str:
            """Путь к файлу иконки вкладки (заглушка до этапа E4)."""
            return ""

        def on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из пользовательского интерфейса вкладки."""
            self._ensure_engine()
            _LOGGER.info("Получено сообщение из вкладки: %s", message)


if _SCRIPT_BASE is not None:

    class FlowSliceWindow(_ConfigMixin, _SCRIPT_BASE):
        """Оконная (script) capability FlowSlice AI."""

        _win: Any = None

        def get_name(self) -> str:
            """Имя capability."""
            return "FlowSlice AI"

        def execute(self) -> orca.ExecutionResult:
            """Открывает окно ассистента либо сообщает, что оно уже открыто."""
            self._ensure_engine()
            win = getattr(self, "_win", None)
            if win is not None and win.is_open():
                return orca.ExecutionResult.success("Окно FlowSlice AI уже открыто")
            self._win = orca.host.ui.create_window(
                html=HTML_PAGE,
                title="FlowSlice AI",
                on_message=self._on_message,
                on_close=self._on_close,
            )
            return orca.ExecutionResult.success("Окно FlowSlice AI открыто")

        def _on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из окна ассистента."""
            self._ensure_engine()
            _LOGGER.info("Получено сообщение из окна: %s", message)

        def _on_close(self, *_args: Any) -> None:
            """Сбрасывает ссылку на закрытое окно."""
            self._win = None


@orca.plugin
class FlowSlicePlugin(orca.base):
    """Пакет плагина FlowSlice AI: регистрация capability."""

    def register_capabilities(self) -> None:
        """Регистрирует доступную capability в порядке приоритета."""
        if _PAGES_BASE is not None:
            orca.register_capability(FlowSliceTab)
        elif _SCRIPT_BASE is not None:
            orca.register_capability(FlowSliceWindow)
