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

import datetime
import importlib
import json
import logging
import pathlib
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.request

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

# Собственный строгий геометрический знак: стилизованный поток/капля с крестом.
_TAB_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <g fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    <path d="M10 2.5c2.8 3.4 4.5 5.9 4.5 8.2a4.5 4.5 0 0 1-9 0c0-2.3 1.7-4.8 4.5-8.2z"/>
    <path d="M10 10.5v3.2"/>
    <path d="M8.2 12.1h3.6"/>
  </g>
</svg>"""


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
    """Движок плагина: конфигурация, чаты, генерация и контекст слайсера."""

    def __init__(self, cap: Any) -> None:
        """Сохраняет ссылку на capability, загружает конфигурацию и историю чатов."""
        self._cap = cap
        self._persist_lock = threading.Lock()
        self._config = self._normalize_config(self._read_raw_config())
        self._chats: list[dict[str, Any]] = []
        self._active = 0
        self._next_id = 1
        self._msg_counter = 1
        self._gen = False
        self._ctx_tokens = 0
        self._post_sink: Any = None
        self._pending_attachment: dict[str, Any] | None = None
        self._pending_confirm: str | None = None
        self._load_chats()

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

    def set_post_sink(self, sink: Any) -> None:
        """Устанавливает callable для доставки payload в UI."""
        self._post_sink = sink

    # ===== Персист истории чатов =====

    def _load_chats(self) -> None:
        """Загружает историю чатов из файла, при ошибке создаёт пустое состояние."""
        data: dict[str, Any] = {}
        try:
            raw = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Не удалось загрузить историю чатов: %s", exc)
        chats = data.get("chats", [])
        self._chats = list(chats) if isinstance(chats, list) else []
        self._active = self._as_int(data.get("active"), 0)
        self._next_id = self._as_int(data.get("next_id"), 1)
        self._msg_counter = self._as_int(data.get("next_msg_id"), 1)
        if not self._chats:
            self._create_chat()

    def _flatten_chats(self) -> list[dict[str, Any]]:
        """Возвращает копию чатов без тяжёлых вложений для записи на диск.

        Фото (data URI) и текст файлов в памяти сохраняются для превью и API
        текущей сессии, но на диск пишутся только их текстовые пометки.
        """
        result: list[dict[str, Any]] = []
        for chat in self._chats:
            flat_msgs: list[dict[str, Any]] = []
            for msg in chat.get("msgs", []):
                flat = dict(msg)
                if flat.get("image"):
                    flat.pop("image", None)
                    if " [фото]" not in str(flat.get("text", "")):
                        flat["text"] = str(flat.get("text", "")) + " [фото]"
                file_info = flat.get("file")
                if file_info:
                    name = str(file_info.get("name", "файл"))
                    flat["file"] = {"name": name}
                    marker = f" [файл: {name}]"
                    if marker not in str(flat.get("text", "")):
                        flat["text"] = str(flat.get("text", "")) + marker
                flat_msgs.append(flat)
            flat_chat = dict(chat)
            flat_chat["msgs"] = flat_msgs
            result.append(flat_chat)
        return result

    def _save_chats(self) -> None:
        """Сохраняет историю чатов в файл под блокировкой без тяжёлых вложений."""
        payload = {
            "chats": self._flatten_chats(),
            "active": self._active,
            "next_id": self._next_id,
            "next_msg_id": self._msg_counter,
        }
        with self._persist_lock:
            try:
                CHATS_FILE.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except OSError as exc:
                _LOGGER.error("Не удалось сохранить историю чатов: %s", exc)

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        """Приводит значение к целому числу с запасным значением."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ===== Мультичат =====

    def _create_chat(self) -> dict[str, Any]:
        """Создаёт новый чат и делает его активным."""
        chat = {
            "id": self._next_id,
            "title": "Новый чат",
            "updated": time.time(),
            "pinned": False,
            "context_flags": {key: True for key in CONTEXT_OPTIONS},
            "msgs": [],
        }
        self._next_id += 1
        self._chats.append(chat)
        self._active = chat["id"]
        self._ctx_tokens = self._estimate_context_tokens(chat["context_flags"])
        self._save_chats()
        return chat

    def _chat_by_id(self, chat_id: Any) -> dict[str, Any] | None:
        """Возвращает чат по идентификатору либо None."""
        for chat in self._chats:
            if chat.get("id") == chat_id:
                return chat
        return None

    def _active_chat(self) -> dict[str, Any]:
        """Возвращает активный чат, создавая его при необходимости."""
        chat = self._chat_by_id(self._active)
        if chat is None:
            chat = self._create_chat()
        return chat

    def _next_msg_id(self) -> int:
        """Возвращает следующий идентификатор сообщения и инкрементирует счётчик."""
        msg_id = self._msg_counter
        self._msg_counter += 1
        return msg_id

    def _trim_chat(self, chat: dict[str, Any]) -> None:
        """Обрезает историю чата до максимального числа сообщений."""
        msgs = chat.get("msgs", [])
        if len(msgs) > MAX_CHAT_MESSAGES:
            del msgs[: len(msgs) - MAX_CHAT_MESSAGES]

    def _auto_title(self, text: str) -> str:
        """Формирует заголовок чата из первого сообщения."""
        return " ".join(text.split())[:40]

    def _append_assistant(self, text: str) -> None:
        """Добавляет сообщение ассистента в активный чат и обновляет UI."""
        chat = self._active_chat()
        chat["msgs"].append(
            {
                "id": self._next_msg_id(),
                "role": "assistant",
                "text": text,
                "ts": time.time(),
            }
        )
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._send_state()

    def _append_system(self, text: str) -> None:
        """Добавляет системное сообщение в активный чат и обновляет UI."""
        chat = self._active_chat()
        chat["msgs"].append(
            {
                "id": self._next_msg_id(),
                "role": "system",
                "text": text,
                "ts": time.time(),
            }
        )
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._send_state()

    # ===== Диспетчер сообщений =====

    def handle_message(self, message: dict) -> None:
        """Разбирает входящее сообщение из UI и направляет в соответствующий хендлер."""
        msg_type = message.get("type", "")
        if msg_type == "get_state":
            self._handle_get_state()
        elif msg_type == "chat":
            self._handle_chat(message)
        elif msg_type == "new_chat":
            self._handle_new_chat()
        elif msg_type == "pick_chat":
            self._handle_pick_chat(message)
        elif msg_type == "delete_chat":
            self._handle_delete_chat(message)
        elif msg_type == "rename_chat":
            self._handle_rename_chat(message)
        elif msg_type == "toggle_pin":
            self._handle_toggle_pin(message)
        elif msg_type == "stop":
            self._handle_stop()
        elif msg_type == "set_context_flags":
            self._handle_context_flags(message)
        elif msg_type == "regenerate":
            self._handle_regenerate()
        elif msg_type == "save_settings":
            self._handle_save_settings(message)
        elif msg_type == "reset_settings":
            self._handle_reset_settings()
        elif msg_type == "test_key":
            self._handle_test_key()
        elif msg_type == "get_usage":
            self._handle_get_usage(message)
        elif msg_type == "attach_file":
            self._handle_attach_file(message)
        else:
            _LOGGER.warning("Неизвестный тип сообщения из UI: %s", msg_type)

    # ===== Хендлеры =====

    def _handle_get_state(self) -> None:
        """Отправляет полное состояние интерфейса."""
        self._send_state()

    def _send_state(self) -> None:
        """Формирует и отправляет полный снимок состояния в UI."""
        chat = self._active_chat()
        self._post(
            {
                "type": "state",
                "chats": self._chats,
                "active": self._active,
                "settings": {
                    key: self._config[key]
                    for key in ("provider", "model", "theme", "font_size", "font_style")
                },
                "context_flags": chat["context_flags"],
                "context_tokens": self._ctx_tokens,
                "status": "печатает…" if self._gen else "",
            }
        )

    def _handle_chat(self, message: dict) -> None:
        """Обрабатывает отправку или редактирование сообщения пользователя."""
        text = str(message.get("text", "")).strip()
        if not text:
            return
        if text.startswith("/") and self._handle_command(text):
            self._pending_attachment = None
            return
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        self._pending_confirm = None
        chat = self._active_chat()
        edit_id = message.get("edit_id")
        if edit_id is not None:
            self._apply_edit(chat, edit_id, text)
            return
        user_msg = {
            "id": self._next_msg_id(),
            "role": "user",
            "text": text,
            "ts": time.time(),
        }
        if self._pending_attachment is not None:
            user_msg.update(self._pending_attachment)
            self._pending_attachment = None
        chat["msgs"].append(user_msg)
        if chat["title"] == "Новый чат":
            chat["title"] = self._auto_title(text)
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._start_generation(chat["id"], text, user_msg["id"])

    def _apply_edit(self, chat: dict[str, Any], edit_id: Any, text: str) -> None:
        """Заменяет текст отредактированного сообщения и перезапускает генерацию."""
        msgs = chat["msgs"]
        for index, msg in enumerate(msgs):
            if msg.get("id") == edit_id:
                msg["text"] = text
                del msgs[index + 1 :]
                chat["updated"] = time.time()
                self._save_chats()
                self._start_generation(chat["id"], text, edit_id)
                return
        _LOGGER.warning("Не найдено сообщение для редактирования: %s", edit_id)

    def _handle_new_chat(self) -> None:
        """Создаёт новый чат и обновляет интерфейс."""
        self._create_chat()
        self._send_state()

    def _handle_pick_chat(self, message: dict) -> None:
        """Переключает активный чат по идентификатору."""
        chat_id = message.get("id")
        if self._chat_by_id(chat_id) is not None:
            self._active = chat_id
            self._send_state()

    def _handle_delete_chat(self, message: dict) -> None:
        """Удаляет чат и корректирует активный идентификатор."""
        chat_id = message.get("id")
        self._chats = [chat for chat in self._chats if chat.get("id") != chat_id]
        if self._active == chat_id:
            self._active = self._chats[0]["id"] if self._chats else 0
        if not self._chats:
            self._create_chat()
        self._save_chats()
        self._send_state()

    def _handle_rename_chat(self, message: dict) -> None:
        """Переименовывает чат по идентификатору."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        title = str(message.get("title", "")).strip()[:60]
        chat["title"] = title or "Новый чат"
        self._save_chats()
        self._send_state()

    def _handle_toggle_pin(self, message: dict) -> None:
        """Переключает закрепление чата."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        chat["pinned"] = not chat.get("pinned", False)
        self._save_chats()
        self._send_state()

    def _handle_stop(self) -> None:
        """Останавливает текущую генерацию."""
        self._gen = False
        self._post({"type": "status", "text": ""})

    def _handle_context_flags(self, message: dict) -> None:
        """Обновляет флаги контекста активного чата."""
        flags = message.get("flags", {})
        if not isinstance(flags, dict):
            return
        chat = self._active_chat()
        chat["context_flags"] = {
            key: bool(flags.get(key, value))
            for key, value in chat["context_flags"].items()
        }
        self._ctx_tokens = self._estimate_context_tokens(chat["context_flags"])
        self._save_chats()
        self._send_state()

    def _handle_regenerate(self) -> None:
        """Перегенерирует последний ответ ассистента."""
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        chat = self._active_chat()
        msgs = chat["msgs"]
        last_user = None
        for msg in reversed(msgs):
            if msg.get("role") == "user":
                last_user = msg
                break
        if last_user is None:
            return
        index = msgs.index(last_user)
        del msgs[index + 1 :]
        self._save_chats()
        self._start_generation(chat["id"], last_user["text"], last_user["id"])

    def _handle_save_settings(self, message: dict) -> None:
        """Сохраняет настройки, присланные из UI."""
        settings = message.get("settings", {})
        if not isinstance(settings, dict):
            return
        for key in (
            "provider",
            "base_url",
            "model",
            "api_key",
            "custom_base_url",
            "custom_model",
            "theme",
            "font_size",
            "font_style",
        ):
            if key in settings:
                self._config[key] = settings[key]
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": "Настройки сохранены.", "kind": "ok"})

    def _handle_reset_settings(self) -> None:
        """Сбрасывает настройки к заводским значениям."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": "Настройки сброшены к заводским.", "kind": "ok"})

    def _post_settings(self) -> None:
        """Отправляет актуальные настройки в UI."""
        self._post(
            {
                "type": "settings",
                "settings": {
                    key: self._config[key]
                    for key in ("provider", "model", "theme", "font_size", "font_style")
                },
            }
        )

    def _handle_test_key(self) -> None:
        """Запускает проверку API-ключа в фоновом потоке."""
        threading.Thread(target=self._test_key_worker, daemon=True).start()

    def _handle_get_usage(self, message: dict) -> None:
        """Отправляет статистику использования за выбранный период."""
        period = message.get("period", "all")
        snap = self._usage_snapshot(period)
        self._post({"type": "usage", **snap})

    def _handle_attach_file(self, message: dict) -> None:
        """Сохраняет вложение для следующего сообщения."""
        kind = message.get("kind")
        name = str(message.get("name", "файл"))
        data = message.get("data", "")
        if kind == "image":
            if len(data) > MAX_IMAGE_B64:
                self._post(
                    {
                        "type": "toast",
                        "text": "Изображение слишком большое (лимит 6 МБ).",
                        "kind": "err",
                    }
                )
                return
            self._pending_attachment = {"image": data}
        else:
            if len(data) > MAX_FILE_CHARS:
                self._post(
                    {
                        "type": "toast",
                        "text": "Файл слишком большой (лимит 1 МБ).",
                        "kind": "err",
                    }
                )
                return
            self._pending_attachment = {"file": {"name": name, "text": data}}
        self._post({"type": "toast", "text": "Вложение добавлено.", "kind": "ok"})

    # ===== Отправка payload в UI =====

    def _post(self, payload: dict) -> None:
        """Отправляет payload в UI через установленный sink."""
        sink = self._post_sink
        if sink is None:
            return
        try:
            sink(payload)
        except Exception as exc:
            _LOGGER.error("Не удалось отправить payload в UI: %s", exc)

    # ===== Генерация ответа =====

    def _start_generation(self, chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Запускает генерацию ответа в фоновом потоке."""
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": "Генерация уже идёт. Дождитесь завершения или нажмите «Стоп».",
                    "kind": "err",
                }
            )
            return
        self._gen = True
        threading.Thread(
            target=self._worker, args=(chat_id, user_text, user_msg_id), daemon=True
        ).start()

    def _worker(self, chat_id: int, user_text: str, user_msg_id: int) -> None:
        """Выполняет запрос к API в фоновом потоке и стримит ответ."""
        chat = self._chat_by_id(chat_id)
        if chat is None:
            self._gen = False
            return
        msg_id = self._next_msg_id()
        chat["msgs"].append(
            {"id": msg_id, "role": "assistant", "text": "", "ts": time.time()}
        )
        self._save_chats()
        self._post({"type": "status", "text": "печатает…"})
        try:
            messages = self._build_messages(chat, user_text)
            full_text = self._call_api(messages, chat_id)
            if not full_text.strip():
                full_text = "Модель вернула пустой ответ."
            msg = self._find_msg(chat, msg_id)
            if msg is not None:
                msg["text"] = full_text
            self._post({"type": "reply", "chat_id": chat_id, "text": full_text, "ok": True})
            self._record_usage(user_text, full_text)
        except FlowSliceError as exc:
            self._fail_generation(chat, chat_id, user_msg_id, msg_id, str(exc))
        except Exception as exc:
            _LOGGER.error("Необработанная ошибка генерации: %s", exc)
            self._fail_generation(
                chat, chat_id, user_msg_id, msg_id, "Внутренняя ошибка генерации."
            )
        finally:
            self._gen = False
            self._post({"type": "status", "text": ""})
            self._save_chats()

    def _fail_generation(
        self,
        chat: dict[str, Any],
        chat_id: int,
        user_msg_id: int,
        msg_id: int,
        text: str,
    ) -> None:
        """Помечает генерацию как ошибочную и уведомляет UI."""
        self._remove_msg(chat, user_msg_id)
        msg = self._find_msg(chat, msg_id)
        if msg is not None:
            msg["text"] = text
            msg["error"] = True
        self._post({"type": "reply", "chat_id": chat_id, "text": text, "ok": False})

    def _find_msg(self, chat: dict[str, Any], msg_id: int) -> dict[str, Any] | None:
        """Возвращает сообщение чата по идентификатору либо None."""
        for msg in chat.get("msgs", []):
            if msg.get("id") == msg_id:
                return msg
        return None

    def _remove_msg(self, chat: dict[str, Any], msg_id: int) -> None:
        """Удаляет сообщение из чата по идентификатору."""
        msgs = chat.get("msgs", [])
        for index, msg in enumerate(msgs):
            if msg.get("id") == msg_id:
                del msgs[index]
                return

    def _collect_context_images(self, chat: dict[str, Any]) -> list[str]:
        """Собирает data URI изображений из последних сообщений чата."""
        images: list[str] = []
        for msg in reversed(chat.get("msgs", [])):
            image = msg.get("image")
            if not isinstance(image, str) or not image.startswith("data:"):
                continue
            images.append(image)
            if len(images) >= MAX_IMAGES_IN_HISTORY:
                break
        return images

    def _build_messages(self, chat: dict[str, Any], user_text: str) -> list[dict[str, Any]]:
        """Собирает список сообщений для запроса к модели."""
        flags = chat.get("context_flags", {})
        ctx = self._collect_context(flags)
        system = self._build_system_prompt(ctx)
        if len(system) > MAX_CONTEXT_CHARS:
            system = system[:MAX_CONTEXT_CHARS]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if flags.get("history"):
            messages.extend(self._history_messages(chat, MAX_CONTEXT_CHARS))
        user_content = user_text
        last_user = self._last_user_msg(chat)
        if last_user is not None and last_user.get("file"):
            file_info = last_user["file"]
            user_content += (
                "\n\n[Файл: " + str(file_info.get("name", "файл")) + "]\n"
                + str(file_info.get("text", ""))
            )
        images = self._collect_context_images(chat)
        if images and self._config.get("provider") != "deepseek":
            content: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
            content.extend(
                {"type": "image_url", "image_url": {"url": img}} for img in images
            )
            messages.append({"role": "user", "content": content})
        else:
            if images:
                user_content += (
                    "\n[Прикреплено изображений: "
                    + str(len(images))
                    + ". Модель DeepSeek не поддерживает изображения]"
                )
            messages.append({"role": "user", "content": user_content})
        return messages

    def _last_user_msg(self, chat: dict[str, Any]) -> dict[str, Any] | None:
        """Возвращает последнее сообщение пользователя в чате."""
        for msg in reversed(chat.get("msgs", [])):
            if msg.get("role") == "user":
                return msg
        return None

    def _history_messages(self, chat: dict[str, Any], max_chars: int) -> list[dict[str, Any]]:
        """Собирает историю сообщений для контекста, отбрасывая старые."""
        msgs = chat.get("msgs", [])
        last_user = self._last_user_msg(chat)
        history = msgs
        if last_user is not None:
            history = msgs[: msgs.index(last_user)]
        result: list[dict[str, Any]] = []
        total = 0
        for msg in reversed(history):
            if msg.get("role") not in ("user", "assistant"):
                continue
            text = str(msg.get("text", ""))
            if msg.get("image"):
                text += " [фото]"
            if msg.get("file"):
                text += " [файл: " + str(msg.get("file", {}).get("name", "файл")) + "]"
            if total + len(text) > max_chars:
                break
            result.append({"role": msg["role"], "content": text})
            total += len(text)
        result.reverse()
        return result

    def _call_api(self, messages: list[dict[str, Any]], chat_id: int) -> str:
        """Выполняет запрос к API провайдера и возвращает полный текст ответа."""
        cfg = self._config
        if cfg.get("provider") != "custom":
            base_url = str(cfg.get("base_url", ""))
            model = str(cfg.get("model", ""))
        else:
            base_url = str(cfg.get("custom_base_url", ""))
            model = str(cfg.get("custom_model", ""))
        if not cfg.get("api_key"):
            raise ApiError("Пожалуйста, укажите API-ключ в настройках.")
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": messages, "stream": True}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + str(cfg["api_key"])},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return self._read_sse(resp, chat_id)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise ApiError("Ошибка API " + str(exc.code) + ": " + body) from exc
        except urllib.error.URLError as exc:
            raise NetworkError("Сетевая ошибка: " + str(exc.reason)) from exc
        except TimeoutError as exc:
            raise NetworkError("Превышен таймаут запроса.") from exc
        except PermissionError as exc:
            raise NetworkError(
                "Сетевой доступ запрещён песочницей. Разрешите сеть для плагина."
            ) from exc
        except OSError as exc:
            raise NetworkError("Ошибка соединения: " + str(exc)) from exc

    def _read_sse(self, resp: Any, chat_id: int) -> str:
        """Читает SSE-поток ответа и отправляет инкрементальные куски в UI."""
        acc = ""
        sent = ""
        last_post = 0.0
        for raw in resp:
            if not self._gen:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content", "")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if not delta:
                continue
            acc += delta
            now = time.monotonic()
            if now - last_post >= STREAM_THROTTLE:
                self._post({"type": "delta", "chat_id": chat_id, "text": delta})
                last_post = now
                sent += delta
        if acc and sent != acc:
            self._post({"type": "delta", "chat_id": chat_id, "text": acc[len(sent) :]})
        return acc

    def _test_key_worker(self) -> None:
        """Проверяет API-ключ фоновым запросом к провайдеру."""
        cfg = self._config
        if not cfg.get("api_key"):
            self._post({"type": "key_test", "ok": False, "text": "API-ключ не указан."})
            return
        if cfg.get("provider") != "custom":
            base_url = str(cfg.get("base_url", ""))
            model = str(cfg.get("model", ""))
        else:
            base_url = str(cfg.get("custom_base_url", ""))
            model = str(cfg.get("custom_model", ""))
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**HTTP_HEADERS, "Authorization": "Bearer " + str(cfg["api_key"])},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                resp.read()
            self._post({"type": "key_test", "ok": True, "text": "Ключ действителен."})
        except urllib.error.HTTPError as exc:
            self._post(
                {"type": "key_test", "ok": False, "text": "Ошибка API " + str(exc.code) + "."}
            )
        except OSError as exc:
            self._post(
                {"type": "key_test", "ok": False, "text": "Сетевая ошибка: " + str(exc)}
            )

    # ===== Контекст слайсера =====

    def _collect_context(self, flags: dict[str, Any]) -> dict[str, Any]:
        """Собирает контекст слайсера по включённым флагам."""
        ctx: dict[str, Any] = {}
        if flags.get("model"):
            ctx["model"] = self._collect_model_data()
        if flags.get("filament") or flags.get("printer") or flags.get("print"):
            ctx["presets"] = self._collect_preset_data()
        return ctx

    def _collect_model_data(self) -> dict[str, Any]:
        """Собирает данные о модели на столе слайсера."""
        data: dict[str, Any] = {"objects": [], "coords": "world"}
        try:
            model = orca.host.model()
            for obj in model.objects():
                for vol in obj.volumes():
                    mesh = vol.mesh()
                    entry: dict[str, Any] = {
                        "name": vol.name(),
                        "local_bbox_mm": tuple(
                            round(v, 1) for v in mesh.bounding_box().size
                        ),
                        "volume_cm3": round(mesh.volume() / 1000.0, 2),
                        "manifold": mesh.is_manifold(),
                        "triangles": mesh.triangle_count(),
                    }
                    if _HAS_NUMPY:
                        entry.update(self._world_stats(obj, vol, mesh))
                    else:
                        entry["coords"] = "local"
                        entry.update(self._local_stats(obj))
                    data["objects"].append(entry)
        except RuntimeError:
            data["objects"] = []
        return data

    def _world_stats(self, obj: Any, vol: Any, mesh: Any) -> dict[str, Any]:
        """Считает мировые характеристики экземпляров через numpy."""
        assert _np is not None
        stats: dict[str, Any] = {"instances": []}
        try:
            verts = mesh.vertices()
            tris = mesh.triangles()
            vol_matrix = vol.matrix()
            instances = obj.instances()
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_list = [obj.instance(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                inst_matrix = inst.matrix()
                world = (
                    _np.column_stack(
                        (verts.astype(_np.float64), _np.ones(len(verts)))
                    )
                    @ (inst_matrix @ vol_matrix).T
                )[:, :3]
                bbox_min = world.min(axis=0)
                bbox_max = world.max(axis=0)
                tri_pts = world[tris]
                cross = _np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                area = float(_np.sum(_np.linalg.norm(cross, axis=1) / 2.0))
                stats["instances"].append(
                    {
                        "index": index,
                        "position_mm": tuple(
                            round(v, 1) for v in inst_matrix[:3, 3]
                        ),
                        "world_bbox_mm": tuple(
                            round(v, 1) for v in (bbox_max - bbox_min)
                        ),
                        "surface_area_cm2": round(area / 100.0, 2),
                        "mirrored": bool(inst.is_left_handed()),
                    }
                )
        except (ImportError, RuntimeError, ValueError):
            stats = {}
        return stats

    def _local_stats(self, obj: Any) -> dict[str, Any]:
        """Собирает локальные характеристики экземпляров без numpy."""
        stats: dict[str, Any] = {"instances": []}
        try:
            instances = obj.instances()
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_list = [obj.instance(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                stats["instances"].append(
                    {
                        "index": index,
                        "offset": tuple(
                            round(v, 1) for v in self._safe_get(inst, "offset")
                        ),
                        "rotation": tuple(
                            round(v, 1) for v in self._safe_get(inst, "rotation")
                        ),
                        "scaling_factor": tuple(
                            round(v, 2) for v in self._safe_get(inst, "scaling_factor")
                        ),
                        "mirrored": bool(self._safe_get(inst, "mirror")),
                    }
                )
        except (RuntimeError, ValueError, TypeError):
            stats = {}
        return stats

    @staticmethod
    def _safe_get(target: Any, name: str) -> Any:
        """Безопасно читает атрибут или метод объекта."""
        value = getattr(target, name, None)
        if callable(value):
            try:
                value = value()
            except (TypeError, RuntimeError):
                value = None
        return value

    def _collect_preset_data(self) -> dict[str, Any]:
        """Собирает данные активных пресетов печати."""
        out: dict[str, Any] = {"printer": {}, "filament": {}, "print": {}}
        try:
            bundle = orca.host.preset_bundle()
        except RuntimeError:
            return out
        candidates = {
            "printer": (
                "name",
                "model",
                "vendor",
                "bed_size",
                "nozzle_diameter",
                "nozzle_type",
                "firmware",
            ),
            "filament": (
                "name",
                "material",
                "density",
                "diameter",
                "temperature",
                "bed_temperature",
                "chamber_temperature",
            ),
            "print": (
                "layer_height",
                "infill",
                "spiral_vase",
                "speed",
                "temperature",
                "fan_speed",
                "brim_width",
            ),
        }
        for key, fields in candidates.items():
            try:
                section = getattr(bundle, key, None)
                if section is None:
                    continue
                out[key] = self._extract_preset_fields(section, fields)
            except (AttributeError, RuntimeError):
                continue
        return out

    def _extract_preset_fields(
        self, section: Any, candidates: tuple[str, ...]
    ) -> dict[str, Any]:
        """Извлекает доступные поля пресета, сохраняя простые типы."""
        result: dict[str, Any] = {}
        for field in candidates:
            value = self._safe_get(section, field)
            if isinstance(value, (str, int, float, bool, tuple, list)):
                result[field] = value
        return result

    def _build_system_prompt(self, ctx: dict[str, Any]) -> str:
        """Собирает системный промпт с данными контекста слайсера."""
        parts = [SYSTEM_PROMPT]
        if ctx.get("model"):
            parts.append(
                "Данные модели со стола:\n"
                + json.dumps(ctx["model"], ensure_ascii=False, indent=2)
            )
        if ctx.get("presets"):
            parts.append(
                "Профили печати:\n"
                + json.dumps(ctx["presets"], ensure_ascii=False, indent=2)
            )
        parts.append(
            "Окружение: Python "
            + sys.version.split()[0]
            + ", дата/время: "
            + time.strftime("%Y-%m-%d %H:%M")
        )
        return "\n\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Грубо оценивает число токенов в тексте."""
        return len(text) // 4

    def _estimate_context_tokens(self, flags: dict[str, Any]) -> int:
        """Оценивает число токенов контекста по флагам."""
        ctx = self._collect_context(flags)
        return self._estimate_tokens(json.dumps(ctx, ensure_ascii=False))

    # ===== Команды =====

    def _handle_command(self, text: str) -> bool:
        """Обрабатывает служебные команды, начинающиеся со слэша."""
        stripped = text.strip()
        if not stripped:
            return False
        cmd = stripped.split()[0].lower()
        if cmd == "/context":
            self._cmd_context()
        elif cmd == "/clear":
            self._cmd_clear()
        elif cmd == "/model":
            self._cmd_model()
        elif cmd == "/printer":
            self._cmd_printer()
        elif cmd == "/stats":
            self._cmd_stats()
        elif cmd == "/help":
            self._cmd_help()
        elif cmd == "/reset":
            self._cmd_reset()
        else:
            return False
        return True

    def _cmd_help(self) -> None:
        """Выводит список доступных команд."""
        lines = [
            "Доступные команды:",
            "/context — полный дамп контекста слайсера",
            "/clear — очистить историю чата",
            "/model — отчёт о модели на столе",
            "/printer — сводка профилей печати",
            "/stats — статистика использования",
            "/help — этот список",
            "/reset — сбросить настройки к заводским",
        ]
        self._append_assistant("\n".join(lines))

    def _cmd_model(self) -> None:
        """Формирует отчёт о модели на столе."""
        data = self._collect_model_data()
        objects = data.get("objects", [])
        if not objects:
            self._append_assistant("Модель на столе отсутствует или недоступна.")
            return
        lines = ["Отчёт о модели на столе:"]
        for obj in objects:
            lines.append("• " + str(obj.get("name", "Без имени")))
            lines.append("  Локальный bbox, мм: " + str(obj.get("local_bbox_mm", "—")))
            lines.append("  Объём: " + str(obj.get("volume_cm3", "—")) + " см³")
            lines.append(
                "  Площадь поверхности: " + str(obj.get("surface_area_cm2", "—")) + " см²"
            )
            lines.append("  Треугольники: " + str(obj.get("triangles", "—")))
            lines.append("  Manifold: " + ("да" if obj.get("manifold") else "нет"))
            for inst in obj.get("instances", []):
                line = "  Экземпляр " + str(inst.get("index", "—"))
                if inst.get("mirrored"):
                    line += " — ЗЕРКАЛЬНЫЙ экземпляр"
                lines.append(line)
        self._append_assistant("\n".join(lines))

    def _cmd_printer(self) -> None:
        """Формирует сводку профилей печати."""
        data = self._collect_preset_data()
        lines = ["Сводка профилей печати:"]
        sections = (
            ("printer", "Принтер"),
            ("filament", "Пластик"),
            ("print", "Настройки печати"),
        )
        for key, label in sections:
            section = data.get(key, {})
            if not section:
                lines.append("• " + label + ": недоступно")
                continue
            lines.append("• " + label + ":")
            for field, value in section.items():
                lines.append("  " + str(field) + ": " + str(value))
        self._append_assistant("\n".join(lines))

    def _cmd_stats(self) -> None:
        """Выводит статистику использования ассистента."""
        snap = self._usage_snapshot("all")
        self._append_assistant(
            "Сообщений: " + str(snap["msgs"]) + ", Токенов: " + str(snap["tokens"])
        )

    def _cmd_context(self) -> None:
        """Выводит полный дамп контекста слайсера."""
        chat = self._active_chat()
        flags = chat.get("context_flags", {})
        ctx = self._collect_context(flags)
        lines = ["Контекст слайсера:"]
        lines.append("Системный промпт:")
        lines.append(self._build_system_prompt(ctx))
        lines.append("Чекбоксы контекста:")
        for key, value in flags.items():
            lines.append("  " + str(key) + ": " + ("вкл" if value else "выкл"))
        lines.append("Данные контекста:")
        lines.append(json.dumps(ctx, ensure_ascii=False, indent=2))
        lines.append("История сообщений:")
        history = self._history_messages(chat, MAX_CONTEXT_CHARS)
        if history:
            for item in history:
                lines.append("  [" + item["role"] + "] " + item["content"][:200])
        else:
            lines.append("  (пусто)")
        lines.append(
            "Оценка токенов контекста: " + str(self._estimate_context_tokens(flags))
        )
        self._append_assistant("\n".join(lines))

    def _confirm_command(self, cmd: str) -> bool:
        """Реализует двухшаговое подтверждение деструктивной команды."""
        if self._pending_confirm != cmd:
            self._pending_confirm = cmd
            self._append_system("Подтвердите: отправьте " + cmd + " ещё раз.")
            return False
        self._pending_confirm = None
        return True

    def _cmd_clear(self) -> None:
        """Очищает историю чата с двухшаговым подтверждением."""
        if not self._confirm_command("/clear"):
            return
        chat = self._active_chat()
        chat["msgs"] = []
        chat["title"] = "Новый чат"
        chat["updated"] = time.time()
        self._ctx_tokens = 0
        self._save_chats()
        self._append_system("История чата очищена.")

    def _cmd_reset(self) -> None:
        """Сбрасывает настройки с двухшаговым подтверждением."""
        if not self._confirm_command("/reset"):
            return
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._cap.save_config(json.dumps(self._config))
        self._append_system("Настройки сброшены к заводским.")

    # ===== Статистика использования =====

    def _record_usage(self, user_text: str, answer_text: str) -> None:
        """Учитывает сообщение и токены в статистике использования."""
        today = time.strftime("%Y-%m-%d")
        usage = self._config.setdefault("usage", {})
        day = usage.setdefault(today, {"msgs": 0, "tokens": 0})
        day["msgs"] += 1
        day["tokens"] += (len(user_text) + len(answer_text)) // 4
        self._cap.save_config(json.dumps(self._config))

    def _usage_snapshot(self, period: str) -> dict[str, Any]:
        """Возвращает сводку использования за выбранный период."""
        usage = self._config.get("usage", {})
        today = time.strftime("%Y-%m-%d")
        if period == "day":
            keys = [today]
        elif period == "week":
            keys = [
                (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
                for i in range(7)
            ]
        elif period == "month":
            keys = [key for key in usage if key.startswith(today[:7])]
        else:
            keys = list(usage)
        msgs = sum(usage.get(key, {}).get("msgs", 0) for key in keys)
        tokens = sum(usage.get(key, {}).get("tokens", 0) for key in keys)
        return {"period": period, "msgs": msgs, "tokens": tokens}


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
        """Лениво создаёт общий движок плагина и подключает sink."""
        engine = getattr(self, "_engine", None)
        if engine is None:
            engine = _ChatEngine(self)
            engine.set_post_sink(self._make_post_sink())
            self._engine = engine
        return engine

    def _make_post_sink(self) -> Any:
        """Возвращает callable для доставки payload в UI."""
        if _PAGES_BASE is not None and isinstance(self, _PAGES_BASE):
            return getattr(self, "post_message", self._window_post)
        return self._window_post

    def _window_post(self, payload: dict) -> None:
        """Отправляет payload в открытое окно ассистента."""
        win = getattr(self, "_win", None)
        if win is not None and win.is_open():
            win.post(payload)


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
            """Записывает иконку вкладки и возвращает путь к файлу."""
            try:
                ICON_FILE.write_text(_TAB_ICON_SVG, encoding="utf-8")
                return str(ICON_FILE)
            except OSError as exc:
                _LOGGER.error("Не удалось записать иконку вкладки: %s", exc)
                return ""

        def on_message(self, message: dict) -> None:
            """Обрабатывает сообщение из пользовательского интерфейса вкладки."""
            self._ensure_engine().handle_message(message)


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
            self._ensure_engine().handle_message(message)

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
