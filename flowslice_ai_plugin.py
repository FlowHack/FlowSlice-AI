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
# pylint: disable=too-many-lines
# HTML_PAGE — большая встроенная строка, из-за неё модуль превышает лимит строк.

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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlowSlice AI</title>
<style>
/* ===== Базовые переменные и темизация ===== */
* {
  box-sizing: border-box;
}
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
}
body {
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
  background: var(--orca-bg);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
  overflow: hidden;
}
/* Принудительная чисто белая тема */
body.theme-light {
  --orca-bg: #ffffff;
  --orca-fg: #1a1a1a;
  --orca-muted: #6b6b6b;
  --orca-border: #d9d9d9;
  --orca-input: #f5f5f5;
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
}
/* Принудительная чисто чёрная тема */
body.theme-dark {
  --orca-bg: #000000;
  --orca-fg: #e6e6e6;
  --orca-muted: #8a8a8a;
  --orca-border: #2a2a2a;
  --orca-input: #141414;
  --orca-accent: #d9534f;
  --orca-accent-fg: #ffffff;
}
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-thumb {
  background: var(--orca-border);
  border-radius: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}

/* ===== Каркас приложения ===== */
.app {
  display: flex;
  height: 100vh;
}

/* ===== Sidebar чатов ===== */
.sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--orca-border);
  display: flex;
  flex-direction: column;
  background: var(--orca-bg);
}
.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--orca-border);
}
.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--orca-muted);
  margin-bottom: 8px;
}
.sidebar-search {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.sidebar-search:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.chat-group {
  font-size: 11px;
  color: var(--orca-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 8px 6px 4px;
}
.chat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
}
.chat-item:hover {
  background: var(--orca-input);
}
.chat-item.active {
  background: var(--orca-input);
  box-shadow: inset 2px 0 0 var(--orca-accent);
}
.chat-title {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.chat-actions {
  display: none;
  gap: 2px;
}
.chat-item:hover .chat-actions {
  display: flex;
}
.chat-action {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 3px;
  border-radius: 4px;
  color: var(--orca-muted);
}
.chat-action:hover {
  background: var(--orca-border);
  color: var(--orca-fg);
}
.sidebar-empty {
  padding: 12px 8px;
  font-size: 12px;
  color: var(--orca-muted);
  text-align: center;
}

/* ===== Основная область ===== */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--orca-border);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #d9534f;
}
.brand-name {
  font-weight: 700;
  font-size: 15px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-status {
  font-size: 12px;
  color: var(--orca-muted);
  margin-right: 4px;
}
.icon-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-fg);
  border-radius: 6px;
  padding: 5px 9px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.icon-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}

/* ===== Область сообщений ===== */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.msg-wrap {
  display: flex;
  flex-direction: column;
  max-width: 78%;
}
.msg-user {
  align-self: flex-end;
  align-items: flex-end;
}
.msg-assistant {
  align-self: flex-start;
}
.msg-system {
  align-self: center;
}
.msg-bubble {
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .msg-bubble {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-bottom-right-radius: 2px;
}
.msg-assistant .msg-bubble {
  background: var(--orca-input);
  border-bottom-left-radius: 2px;
}
.msg-error .msg-bubble {
  border: 1px solid var(--orca-accent);
  background: var(--orca-input);
}
.msg-system .msg-bubble {
  background: transparent;
  color: var(--orca-muted);
  font-size: 12px;
  padding: 2px 8px;
}
.msg-time {
  font-size: 10px;
  color: var(--orca-muted);
  margin-top: 3px;
}
.msg-image {
  max-width: 100%;
  max-height: 240px;
  border-radius: 8px;
  margin-bottom: 6px;
  display: block;
}
.msg-actions {
  display: none;
  gap: 4px;
  margin-top: 4px;
}
.msg-wrap:hover .msg-actions {
  display: flex;
}
.msg-action {
  border: 1px solid var(--orca-border);
  background: var(--orca-bg);
  color: var(--orca-muted);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
}
.msg-action:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.msg-streaming .msg-bubble::after {
  content: "▌";
  color: var(--orca-accent);
  animation: blink 1s infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* ===== Welcome-сообщение ===== */
.welcome {
  align-self: center;
  text-align: center;
  margin-top: 10vh;
  max-width: 480px;
}
.welcome-title {
  font-size: 22px;
  font-weight: 700;
}
.welcome-sub {
  color: var(--orca-muted);
  font-size: 13px;
  margin: 8px 0 16px;
}
.welcome-cmds {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.welcome-cmd {
  border: 1px solid var(--orca-border);
  border-radius: 12px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--orca-muted);
  font-family: Consolas, monospace;
}

/* ===== Индикатор «печатает…» ===== */
.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px 8px;
  color: var(--orca-muted);
  font-size: 12px;
}
.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--orca-accent);
  animation: bounce 1.2s infinite;
}
.typing .dot:nth-child(2) {
  animation-delay: 0.15s;
}
.typing .dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
.typing-text {
  margin-left: 6px;
}

/* ===== Панель контекста ===== */
.context-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  border-top: 1px solid var(--orca-border);
  gap: 8px;
  flex-wrap: wrap;
}
.context-checks {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ctx-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--orca-muted);
  cursor: pointer;
}
.ctx-check input {
  accent-color: var(--orca-accent);
}
.context-tokens {
  font-size: 12px;
  color: var(--orca-muted);
}

/* ===== Композер (input) ===== */
.composer {
  padding: 8px 16px 12px;
  border-top: 1px solid var(--orca-border);
}
.attach-preview {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.attach-card {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  background: var(--orca-input);
}
.attach-card img {
  width: 28px;
  height: 28px;
  object-fit: cover;
  border-radius: 4px;
}
.attach-name {
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.attach-remove {
  border: none;
  background: transparent;
  color: var(--orca-muted);
  cursor: pointer;
  font-size: 12px;
}
.attach-remove:hover {
  color: var(--orca-accent);
}
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.input-row textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--orca-border);
  border-radius: 8px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 14px;
  padding: 9px 12px;
  max-height: 120px;
  line-height: 1.4;
}
.input-row textarea:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.send-btn {
  border: none;
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-radius: 8px;
  padding: 9px 14px;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}
.send-btn:hover {
  filter: brightness(1.1);
}
.stop-btn {
  border: 1px solid var(--orca-accent);
  background: transparent;
  color: var(--orca-accent);
  border-radius: 8px;
  padding: 9px 12px;
  cursor: pointer;
  font-size: 13px;
}
.stop-btn:hover {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}

/* ===== Модалка настроек ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  width: 420px;
  max-width: 92vw;
  max-height: 88vh;
  overflow-y: auto;
  background: var(--orca-bg);
  border: 1px solid var(--orca-border);
  border-radius: 10px;
  padding: 16px;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.modal-header span {
  font-size: 15px;
  font-weight: 600;
}
.field {
  margin-bottom: 12px;
}
.field label {
  display: block;
  font-size: 12px;
  color: var(--orca-muted);
  margin-bottom: 5px;
}
.field select,
.field input[type="text"],
.field input[type="password"] {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-family: var(--orca-font);
  font-size: 13px;
}
.field select:focus,
.field input:focus {
  outline: none;
  border-color: var(--orca-accent);
}
.field input[type="range"] {
  width: 100%;
  accent-color: var(--orca-accent);
}
.key-row {
  display: flex;
  gap: 6px;
}
.key-row input {
  flex: 1;
}
.ghost-btn {
  border: 1px solid var(--orca-border);
  background: transparent;
  color: var(--orca-fg);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.ghost-btn:hover {
  border-color: var(--orca-accent);
  color: var(--orca-accent);
}
.usage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.usage-row select {
  padding: 5px 8px;
  border: 1px solid var(--orca-border);
  border-radius: 6px;
  background: var(--orca-input);
  color: var(--orca-fg);
  font-size: 12px;
}
.usage-row span {
  font-size: 12px;
  color: var(--orca-muted);
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.danger-btn {
  border: 1px solid var(--orca-accent);
  background: transparent;
  color: var(--orca-accent);
  border-radius: 6px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
}
.danger-btn:hover {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.primary-btn {
  border: none;
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
  border-radius: 6px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: 13px;
}
.primary-btn:hover {
  filter: brightness(1.1);
}

/* ===== Toast-уведомления ===== */
.toast {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--orca-fg);
  color: var(--orca-bg);
  border-radius: 8px;
  padding: 9px 16px;
  font-size: 13px;
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  transition: opacity 0.3s;
}
.toast-ok {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.toast-err {
  background: var(--orca-accent);
  color: var(--orca-accent-fg);
}
.toast-hide {
  opacity: 0;
}
</style>
</head>
<body>
<div class="app">
  <!-- Sidebar чатов -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">Чаты</div>
      <input type="text" id="searchInput" class="sidebar-search" placeholder="Поиск чатов…">
    </div>
    <div class="chat-list" id="chatList"></div>
  </aside>

  <!-- Основная область -->
  <section class="main">
    <header class="main-header">
      <div class="brand">
        <span class="brand-dot"></span>
        <span class="brand-name">FlowSlice AI</span>
      </div>
      <div class="header-right">
        <span class="model-status" id="modelStatus"></span>
        <button type="button" id="settingsBtn" class="icon-btn" title="Настройки">⚙</button>
        <button type="button" id="newChatBtn" class="icon-btn" title="Новый чат">+</button>
      </div>
    </header>

    <main class="messages" id="messages"></main>

    <div class="typing" id="typing" style="display:none">
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="typing-text">печатает…</span>
    </div>

    <!-- Панель контекста -->
    <div class="context-panel">
      <div class="context-checks" id="contextChecks"></div>
      <div class="context-tokens" id="contextTokens">≈ 0 токенов</div>
    </div>

    <!-- Композер -->
    <div class="composer">
      <div class="attach-preview" id="attachPreview"></div>
      <div class="input-row">
        <button type="button" id="attachBtn" class="icon-btn" title="Прикрепить файл">📎</button>
        <textarea id="input" rows="1" placeholder="Сообщение… (Enter — отправить, Shift+Enter — новая строка)"></textarea>
        <button type="button" id="stopBtn" class="stop-btn" title="Остановить генерацию" style="display:none">■</button>
        <button type="button" id="sendBtn" class="send-btn" title="Отправить">➤</button>
        <input type="file" id="fileInput" multiple style="display:none">
      </div>
    </div>
  </section>
</div>

<!-- Модалка настроек -->
<div class="modal-overlay" id="settingsModal" style="display:none">
  <div class="modal">
    <div class="modal-header">
      <span>Настройки</span>
      <button type="button" id="modalClose" class="icon-btn" title="Закрыть">✕</button>
    </div>
    <div class="field">
      <label for="setProvider">Провайдер</label>
      <select id="setProvider">
        <option value="deepseek">DeepSeek</option>
        <option value="openrouter">OpenRouter</option>
        <option value="custom">Custom</option>
      </select>
    </div>
    <div class="field" id="setModelWrap">
      <label for="setModel">Модель</label>
      <select id="setModel"></select>
    </div>
    <div class="field" id="setCustomModelWrap" style="display:none">
      <label for="setCustomModel">Идентификатор модели</label>
      <input type="text" id="setCustomModel" placeholder="например, deepseek-chat">
    </div>
    <div class="field" id="setBaseWrap" style="display:none">
      <label for="setBase">Базовый URL API</label>
      <input type="text" id="setBase" placeholder="https://api.example.com/v1">
    </div>
    <div class="field">
      <label for="setApiKey">API-ключ</label>
      <div class="key-row">
        <input type="password" id="setApiKey" autocomplete="off">
        <button type="button" id="testKeyBtn" class="ghost-btn">Проверить ключ</button>
      </div>
    </div>
    <div class="field">
      <label for="setTheme">Тема</label>
      <select id="setTheme">
        <option value="auto">Авто</option>
        <option value="light">Светлая</option>
        <option value="dark">Тёмная</option>
      </select>
    </div>
    <div class="field">
      <label for="setFontSize">Размер шрифта: <span id="setFontSizeValue">14</span> px</label>
      <input type="range" id="setFontSize" min="10" max="20" step="1" value="14">
    </div>
    <div class="field">
      <label for="setFontStyle">Стиль шрифта</label>
      <select id="setFontStyle">
        <option value="system">Системный</option>
        <option value="mono">Моноширинный</option>
        <option value="serif">С засечками</option>
      </select>
    </div>
    <div class="usage-row">
      <select id="setPeriod">
        <option value="day">День</option>
        <option value="week">Неделя</option>
        <option value="month">Месяц</option>
        <option value="all">Всё время</option>
      </select>
      <span id="setUsage">Сообщения: 0 · Токены: 0</span>
    </div>
    <div class="modal-actions">
      <button type="button" id="exportBtn" class="ghost-btn">Экспорт чата</button>
      <button type="button" id="resetSettingsBtn" class="danger-btn">Сбросить</button>
      <button type="button" id="saveSettingsBtn" class="primary-btn">Сохранить</button>
    </div>
  </div>
</div>

<script>
(function () {
  "use strict";

  /* ===== Константы ===== */
  var CONTEXT_KEYS = ["filament", "printer", "print", "model", "history"];
  var CONTEXT_LABELS = {
    filament: "Пластик",
    printer: "Принтер",
    print: "Настройки печати",
    model: "Модель со стола",
    history: "История"
  };
  var MODELS = {
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

  /* ===== Состояние ===== */
  var state = {
    chats: [],
    active: null,
    settings: {},
    context_flags: {},
    context_tokens: 0,
    status: "idle"
  };
  var streamTextEl = null; // элемент текста текущего стримингового сообщения
  var pendingEditId = null; // id сообщения, которое редактируется
  var attachments = []; // вложения перед отправкой
  var userScrolledUp = false; // пользователь прокрутил историю вверх

  /* ===== Хелперы ===== */
  function byId(id) {
    return document.getElementById(id);
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) {
      node.className = cls;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function post(obj) {
    if (window.orca && typeof window.orca.postMessage === "function") {
      window.orca.postMessage(obj);
    }
  }

  function getActiveChat() {
    var chats = state.chats || [];
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === state.active) {
        return chats[i];
      }
    }
    return null;
  }

  function formatTime(ts) {
    if (!ts) {
      return "";
    }
    var d = new Date(ts);
    var h = d.getHours();
    var m = d.getMinutes();
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }

  /* ===== Тема и шрифт ===== */
  function applyTheme(settings) {
    var theme = (settings && settings.theme) || "auto";
    document.body.classList.remove("theme-light", "theme-dark");
    if (theme === "light") {
      document.body.classList.add("theme-light");
    } else if (theme === "dark") {
      document.body.classList.add("theme-dark");
    }
  }

  function applyFont(settings) {
    var size = (settings && settings.font_size) || 14;
    var style = (settings && settings.font_style) || "system";
    document.body.style.fontSize = size + "px";
    if (style === "mono") {
      document.body.style.fontFamily = "Consolas, monospace";
    } else if (style === "serif") {
      document.body.style.fontFamily = "Georgia, serif";
    } else {
      document.body.style.fontFamily = "var(--orca-font)";
    }
  }

  /* ===== Header ===== */
  function renderHeader() {
    var s = state.settings || {};
    var model = s.model || "—";
    var provider = s.provider || "—";
    byId("modelStatus").textContent = model + " · " + provider;
  }

  /* ===== Sidebar ===== */
  function groupChats(chats) {
    var groups = { pinned: [], today: [], yesterday: [], earlier: [] };
    var now = new Date();
    var startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var startOfYesterday = new Date(startOfToday.getTime() - 86400000);
    for (var i = 0; i < chats.length; i++) {
      var chat = chats[i];
      if (chat.pinned) {
        groups.pinned.push(chat);
        continue;
      }
      var d = new Date(chat.updated || 0);
      if (d >= startOfToday) {
        groups.today.push(chat);
      } else if (d >= startOfYesterday) {
        groups.yesterday.push(chat);
      } else {
        groups.earlier.push(chat);
      }
    }
    return groups;
  }

  function sortByUpdated(list) {
    list.sort(function (a, b) {
      return (b.updated || 0) - (a.updated || 0);
    });
  }

  function renameChat(chat) {
    var title = window.prompt("Новое название чата:", chat.title || "");
    if (title !== null) {
      post({ type: "rename_chat", id: chat.id, title: title.trim() || "Новый чат" });
    }
  }

  function deleteChat(chat) {
    if (window.confirm("Удалить чат «" + (chat.title || "Новый чат") + "»?")) {
      post({ type: "delete_chat", id: chat.id });
    }
  }

  function chatItem(chat) {
    var item = el("div", "chat-item" + (chat.id === state.active ? " active" : ""));
    item.appendChild(el("div", "chat-title", chat.title || "Новый чат"));
    var actions = el("div", "chat-actions");
    var pinBtn = el("button", "chat-action", "📌");
    pinBtn.type = "button";
    pinBtn.title = chat.pinned ? "Открепить" : "Закрепить";
    pinBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      post({ type: "toggle_pin", id: chat.id });
    });
    var renameBtn = el("button", "chat-action", "✏️");
    renameBtn.type = "button";
    renameBtn.title = "Переименовать";
    renameBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      renameChat(chat);
    });
    var delBtn = el("button", "chat-action", "🗑");
    delBtn.type = "button";
    delBtn.title = "Удалить";
    delBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      deleteChat(chat);
    });
    actions.appendChild(pinBtn);
    actions.appendChild(renameBtn);
    actions.appendChild(delBtn);
    item.appendChild(actions);
    item.addEventListener("click", function () {
      post({ type: "pick_chat", id: chat.id });
    });
    return item;
  }

  function renderSidebar() {
    var list = byId("chatList");
    list.innerHTML = "";
    var query = byId("searchInput").value.trim().toLowerCase();
    var chats = state.chats || [];
    if (query) {
      // Режим поиска: плоский список совпадений
      var filtered = [];
      for (var i = 0; i < chats.length; i++) {
        if ((chats[i].title || "").toLowerCase().indexOf(query) !== -1) {
          filtered.push(chats[i]);
        }
      }
      for (var j = 0; j < filtered.length; j++) {
        list.appendChild(chatItem(filtered[j]));
      }
      if (filtered.length === 0) {
        list.appendChild(el("div", "sidebar-empty", "Ничего не найдено"));
      }
      return;
    }
    var groups = groupChats(chats);
    sortByUpdated(groups.pinned);
    sortByUpdated(groups.today);
    sortByUpdated(groups.yesterday);
    sortByUpdated(groups.earlier);
    var groupTitles = [
      ["pinned", "Закреплённые"],
      ["today", "Сегодня"],
      ["yesterday", "Вчера"],
      ["earlier", "Ранее"]
    ];
    var any = false;
    for (var g = 0; g < groupTitles.length; g++) {
      var key = groupTitles[g][0];
      var label = groupTitles[g][1];
      var items = groups[key];
      if (items.length === 0) {
        continue;
      }
      any = true;
      list.appendChild(el("div", "chat-group", label));
      for (var k = 0; k < items.length; k++) {
        list.appendChild(chatItem(items[k]));
      }
    }
    if (!any) {
      list.appendChild(el("div", "sidebar-empty", "Чатов пока нет"));
    }
  }

  /* ===== Сообщения ===== */
  function actionBtn(label, handler) {
    var btn = el("button", "msg-action", label);
    btn.type = "button";
    btn.addEventListener("click", handler);
    return btn;
  }

  function renderMessage(msg, index, msgs) {
    var wrap = el("div", "msg-wrap msg-" + msg.role);
    if (msg.error) {
      wrap.classList.add("msg-error");
    }
    if (msg.role === "system") {
      wrap.appendChild(el("div", "msg-bubble", msg.text || ""));
      return wrap;
    }
    var bubble = el("div", "msg-bubble");
    if (msg.image) {
      var img = document.createElement("img");
      img.className = "msg-image";
      img.src = msg.image;
      img.alt = "Вложение";
      bubble.appendChild(img);
    }
    bubble.appendChild(el("div", "msg-text", msg.text || ""));
    bubble.appendChild(el("div", "msg-time", formatTime(msg.ts)));
    wrap.appendChild(bubble);
    var actions = el("div", "msg-actions");
    if (msg.role === "assistant") {
      actions.appendChild(actionBtn("Копировать", function () {
        copyText(msg.text || "");
      }));
      if (index === msgs.length - 1) {
        actions.appendChild(actionBtn("Регенерировать", function () {
          post({ type: "regenerate" });
        }));
      }
    } else if (msg.role === "user") {
      actions.appendChild(actionBtn("Редактировать", function () {
        startEdit(msg);
      }));
    }
    wrap.appendChild(actions);
    return wrap;
  }

  function renderWelcome() {
    var wrap = el("div", "welcome");
    wrap.appendChild(el("div", "welcome-title", "FlowSlice AI"));
    wrap.appendChild(el("div", "welcome-sub", "Инженер-эксперт 3D-печати. Спросите о механике, Klipper или материалах."));
    var list = el("div", "welcome-cmds");
    var cmds = ["/context", "/clear", "/model", "/printer", "/stats", "/help", "/reset"];
    for (var i = 0; i < cmds.length; i++) {
      list.appendChild(el("span", "welcome-cmd", cmds[i]));
    }
    wrap.appendChild(list);
    return wrap;
  }

  function renderMessages() {
    var container = byId("messages");
    container.innerHTML = "";
    streamTextEl = null;
    var chat = getActiveChat();
    if (!chat || !chat.msgs || chat.msgs.length === 0) {
      container.appendChild(renderWelcome());
      return;
    }
    var msgs = chat.msgs;
    for (var i = 0; i < msgs.length; i++) {
      container.appendChild(renderMessage(msgs[i], i, msgs));
    }
    // Ссылка на последнее сообщение assistant для стриминга
    for (var j = msgs.length - 1; j >= 0; j--) {
      if (msgs[j].role === "assistant") {
        var wraps = container.querySelectorAll(".msg-assistant");
        if (wraps.length > 0) {
          var textEl = wraps[wraps.length - 1].querySelector(".msg-text");
          if (textEl) {
            streamTextEl = textEl;
          }
        }
        break;
      }
    }
    scrollToBottom(true);
  }

  function scrollToBottom(force) {
    var container = byId("messages");
    if (force || !userScrolledUp) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function onMessagesScroll() {
    var container = byId("messages");
    var nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    userScrolledUp = !nearBottom;
  }

  /* ===== Панель контекста ===== */
  function renderContext() {
    var container = byId("contextChecks");
    container.innerHTML = "";
    var flags = state.context_flags || {};
    for (var i = 0; i < CONTEXT_KEYS.length; i++) {
      var key = CONTEXT_KEYS[i];
      var checkWrap = el("label", "ctx-check");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!flags[key];
      cb.addEventListener("change", function () {
        var newFlags = {};
        var boxes = container.querySelectorAll("input[type=checkbox]");
        for (var b = 0; b < boxes.length; b++) {
          newFlags[CONTEXT_KEYS[b]] = boxes[b].checked;
        }
        post({ type: "set_context_flags", flags: newFlags });
      });
      checkWrap.appendChild(cb);
      checkWrap.appendChild(document.createTextNode(CONTEXT_LABELS[key] || key));
      container.appendChild(checkWrap);
    }
    byId("contextTokens").textContent = "≈ " + (state.context_tokens || 0) + " токенов";
  }

  /* ===== Индикатор «печатает…» ===== */
  function updateTyping() {
    var streaming = state.status === "streaming";
    byId("typing").style.display = streaming ? "flex" : "none";
    byId("stopBtn").style.display = streaming ? "block" : "none";
  }

  /* ===== Полный ререндер по state ===== */
  function renderState() {
    renderHeader();
    renderSidebar();
    renderContext();
    renderMessages();
    applyTheme(state.settings);
    applyFont(state.settings);
    updateTyping();
  }

  /* ===== Вложения ===== */
  function renderAttachments() {
    var container = byId("attachPreview");
    container.innerHTML = "";
    for (var i = 0; i < attachments.length; i++) {
      var att = attachments[i];
      var card = el("div", "attach-card");
      if (att.kind === "image") {
        var thumb = document.createElement("img");
        thumb.src = att.data;
        thumb.alt = att.name;
        card.appendChild(thumb);
      } else {
        card.appendChild(el("span", "attach-icon", "📄"));
      }
      card.appendChild(el("span", "attach-name", att.name));
      var removeBtn = el("button", "attach-remove", "✕");
      removeBtn.type = "button";
      removeBtn.title = "Убрать вложение";
      removeBtn.addEventListener("click", (function (idx) {
        return function () {
          attachments.splice(idx, 1);
          renderAttachments();
        };
      })(i));
      card.appendChild(removeBtn);
      container.appendChild(card);
    }
  }

  function handleFiles(fileList) {
    var files = Array.prototype.slice.call(fileList);
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      if (file.type && file.type.indexOf("image/") === 0) {
        // Фото: сжатие через canvas до 1024px по большей стороне
        var imgReader = new FileReader();
        imgReader.onload = function (e) {
          var img = new Image();
          img.onload = function () {
            var maxSide = 1024;
            var scale = Math.min(1, maxSide / Math.max(img.width, img.height));
            var w = Math.round(img.width * scale);
            var h = Math.round(img.height * scale);
            var canvas = document.createElement("canvas");
            canvas.width = w;
            canvas.height = h;
            var ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, w, h);
            attachments.push({
              kind: "image",
              name: file.name,
              data: canvas.toDataURL("image/jpeg", 0.85)
            });
            renderAttachments();
          };
          img.src = e.target.result;
        };
        imgReader.readAsDataURL(file);
      } else {
        // Текстовый файл
        var textReader = new FileReader();
        textReader.onload = function (e) {
          attachments.push({
            kind: "text",
            name: file.name,
            data: String(e.target.result)
          });
          renderAttachments();
        };
        textReader.readAsText(file);
      }
    }
  }

  /* ===== Отправка сообщения ===== */
  function sendMessage() {
    var input = byId("input");
    var text = input.value.trim();
    if (!text && attachments.length === 0) {
      return;
    }
    for (var i = 0; i < attachments.length; i++) {
      post({
        type: "attach_file",
        kind: attachments[i].kind,
        name: attachments[i].name,
        data: attachments[i].data
      });
    }
    attachments = [];
    renderAttachments();
    var editId = pendingEditId;
    pendingEditId = null;
    var payload = { type: "chat", text: text };
    if (editId) {
      payload.edit_id = editId;
    }
    post(payload);
    input.value = "";
    autoResize();
    input.focus();
  }

  function startEdit(msg) {
    pendingEditId = msg.id;
    byId("input").value = msg.text || "";
    autoResize();
    byId("input").focus();
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text || "").then(function () {
        showToast("Скопировано", "ok");
      }, function () {
        showToast("Не удалось скопировать", "err");
      });
    } else {
      showToast("Буфер обмена недоступен", "err");
    }
  }

  function autoResize() {
    var input = byId("input");
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  }

  function onInputKey(e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  }

  /* ===== Модалка настроек ===== */
  function renderModelSelect() {
    var provider = byId("setProvider").value;
    var isCustom = provider === "custom";
    byId("setModelWrap").style.display = isCustom ? "none" : "block";
    byId("setCustomModelWrap").style.display = isCustom ? "block" : "none";
    byId("setBaseWrap").style.display = isCustom ? "block" : "none";
    var select = byId("setModel");
    select.innerHTML = "";
    var options = MODELS[provider] || [];
    for (var i = 0; i < options.length; i++) {
      var option = document.createElement("option");
      option.value = options[i].value;
      option.textContent = options[i].label;
      select.appendChild(option);
    }
    var s = state.settings || {};
    if (!isCustom) {
      var matched = false;
      for (var j = 0; j < options.length; j++) {
        if (options[j].value === s.model) {
          matched = true;
        }
      }
      select.value = matched ? s.model : (options.length > 0 ? options[0].value : "");
    }
  }

  function fillSettingsForm() {
    var s = state.settings || {};
    byId("setProvider").value = s.provider || "deepseek";
    byId("setApiKey").value = s.api_key || "";
    byId("setTheme").value = s.theme || "auto";
    byId("setFontSize").value = String(s.font_size || 14);
    byId("setFontSizeValue").textContent = String(s.font_size || 14);
    byId("setFontStyle").value = s.font_style || "system";
    byId("setCustomModel").value = s.custom_model || "";
    byId("setBase").value = s.custom_base_url || "";
    renderModelSelect();
  }

  function openSettings() {
    fillSettingsForm();
    byId("settingsModal").style.display = "flex";
    post({ type: "get_usage", period: byId("setPeriod").value });
  }

  function closeSettings() {
    byId("settingsModal").style.display = "none";
  }

  function saveSettings() {
    var provider = byId("setProvider").value;
    var settings = {
      provider: provider,
      api_key: byId("setApiKey").value,
      theme: byId("setTheme").value,
      font_size: parseInt(byId("setFontSize").value, 10) || 14,
      font_style: byId("setFontStyle").value
    };
    if (provider === "custom") {
      settings.custom_model = byId("setCustomModel").value.trim();
      settings.custom_base_url = byId("setBase").value.trim();
      settings.model = settings.custom_model;
    } else {
      settings.model = byId("setModel").value;
    }
    post({ type: "save_settings", settings: settings });
    closeSettings();
  }

  function exportChat() {
    var chat = getActiveChat();
    if (!chat) {
      showToast("Нет активного чата", "err");
      return;
    }
    var lines = [chat.title || "Чат"];
    var msgs = chat.msgs || [];
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      if (m.role === "user") {
        lines.push("Пользователь: " + (m.text || ""));
      } else if (m.role === "assistant") {
        lines.push("FlowSlice AI: " + (m.text || ""));
      }
    }
    copyText(lines.join("\n\n"));
  }

  function renderUsage(msg) {
    byId("setUsage").textContent = "Сообщения: " + (msg.msgs || 0) + " · Токены: " + (msg.tokens || 0);
  }

  /* ===== Toast ===== */
  function showToast(text, kind) {
    var toast = el("div", "toast" + (kind ? " toast-" + kind : ""), text);
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.classList.add("toast-hide");
    }, 2500);
    setTimeout(function () {
      toast.remove();
    }, 2800);
  }

  /* ===== Обработка входящих сообщений Py→JS ===== */
  function handleDelta(msg) {
    if (msg.chat_id && msg.chat_id !== state.active) {
      return;
    }
    if (!streamTextEl) {
      // Стриминг начался без полного state — создаём сообщение на лету
      var chat = getActiveChat();
      if (!chat) {
        return;
      }
      chat.msgs = chat.msgs || [];
      chat.msgs.push({ id: "stream", role: "assistant", text: "", ts: Date.now() });
      var node = renderMessage(chat.msgs[chat.msgs.length - 1], chat.msgs.length - 1, chat.msgs);
      node.classList.add("msg-streaming");
      byId("messages").appendChild(node);
      streamTextEl = node.querySelector(".msg-text");
    }
    streamTextEl.textContent += msg.text || "";
    scrollToBottom(false);
  }

  function handleReply(msg) {
    if (msg.chat_id && msg.chat_id !== state.active) {
      return;
    }
    if (streamTextEl) {
      streamTextEl.textContent = msg.text || "";
      var node = streamTextEl.closest(".msg-wrap");
      if (node) {
        node.classList.remove("msg-streaming");
        if (!msg.ok) {
          node.classList.add("msg-error");
        }
      }
      streamTextEl = null;
    } else {
      // Ответ без стриминга — добавляем сообщение целиком
      var chat = getActiveChat();
      if (!chat) {
        return;
      }
      chat.msgs = chat.msgs || [];
      chat.msgs.push({
        id: "r" + Date.now(),
        role: "assistant",
        text: msg.text || "",
        ts: Date.now(),
        error: !msg.ok
      });
      renderMessages();
    }
    state.status = "idle";
    updateTyping();
    scrollToBottom(false);
  }

  function onMessage(msg) {
    if (!msg || typeof msg !== "object") {
      return;
    }
    switch (msg.type) {
      case "state":
        state.chats = msg.chats || [];
        state.active = msg.active || null;
        state.settings = msg.settings || {};
        state.context_flags = msg.context_flags || {};
        state.context_tokens = msg.context_tokens || 0;
        state.status = msg.status || "idle";
        renderState();
        break;
      case "delta":
        handleDelta(msg);
        break;
      case "reply":
        handleReply(msg);
        break;
      case "status":
        state.status = msg.text || "idle";
        updateTyping();
        break;
      case "toast":
        showToast(msg.text || "", msg.kind || "");
        break;
      case "chats":
        state.chats = msg.chats || [];
        state.active = msg.active || null;
        renderSidebar();
        break;
      case "settings":
        state.settings = msg.settings || {};
        applyTheme(state.settings);
        applyFont(state.settings);
        fillSettingsForm();
        renderHeader();
        break;
      case "key_test":
        showToast(msg.text || (msg.ok ? "Ключ действителен" : "Ключ недействителен"), msg.ok ? "ok" : "err");
        break;
      case "usage":
        renderUsage(msg);
        break;
    }
  }

  /* ===== Инициализация ===== */
  function init() {
    byId("sendBtn").addEventListener("click", sendMessage);
    byId("stopBtn").addEventListener("click", function () {
      post({ type: "stop" });
    });
    byId("attachBtn").addEventListener("click", function () {
      byId("fileInput").click();
    });
    byId("fileInput").addEventListener("change", function () {
      handleFiles(this.files);
      this.value = "";
    });
    byId("input").addEventListener("keydown", onInputKey);
    byId("input").addEventListener("input", autoResize);
    byId("newChatBtn").addEventListener("click", function () {
      post({ type: "new_chat" });
    });
    byId("settingsBtn").addEventListener("click", openSettings);
    byId("modalClose").addEventListener("click", closeSettings);
    byId("settingsModal").addEventListener("click", function (e) {
      if (e.target === this) {
        closeSettings();
      }
    });
    byId("saveSettingsBtn").addEventListener("click", saveSettings);
    byId("resetSettingsBtn").addEventListener("click", function () {
      post({ type: "reset_settings" });
    });
    byId("testKeyBtn").addEventListener("click", function () {
      post({ type: "test_key" });
    });
    byId("exportBtn").addEventListener("click", exportChat);
    byId("setProvider").addEventListener("change", renderModelSelect);
    byId("setPeriod").addEventListener("change", function () {
      post({ type: "get_usage", period: this.value });
    });
    byId("searchInput").addEventListener("input", renderSidebar);
    byId("messages").addEventListener("scroll", onMessagesScroll);

    if (window.orca && typeof window.orca.onMessage === "function") {
      window.orca.onMessage(onMessage);
    }
    post({ type: "get_state" });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
</script>
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
