"""Ядро движка FlowSlice AI: конфигурация, чаты, состояние и базовые хелперы.

Миксин CoreMixin собирает методы управления конфигурацией (нормализация,
миграция, синхронизация), персистом истории чатов и отправкой состояния в UI.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-statements,too-many-branches,broad-exception-caught
# pylint: disable=too-many-locals,too-many-public-methods,too-many-nested-blocks,too-few-public-methods
# pylint: disable=too-many-return-statements

import json
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.config import (
    COMMANDS,
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    SETTINGS_KEYS,
    normalize_max_tokens,
    normalize_temperature,
)
from flowslice_ai.constants import (
    CONTEXT_OPTIONS,
    MAX_CHAT_MESSAGES,
    MAX_PERSISTED_FILE_CHARS,
    PRESET_CONTEXT_KEYS,
)
from flowslice_ai.i18n import I18N_PY
from flowslice_ai.logging import _LOGGER
from flowslice_ai.paths import CHATS_FILE, atomic_write_text
from flowslice_ai.providers_data import DEFAULT_PROVIDERS


class CoreMixin:
    """Конфигурация, чаты, состояние и базовые хелперы движка."""

    def __init__(self: "_ChatEngine", cap: Any) -> None:
        """Сохраняет ссылку на capability, загружает конфигурацию и историю чатов."""
        self._cap = cap
        self._persist_lock = threading.Lock()
        self._gen_lock = threading.Lock()
        # Защищает однократный фоновый запуск уточнения зрения и кэш контекста.
        self._vision_lock = threading.Lock()
        self._context_lock = threading.Lock()
        self._config = self._normalize_config(self._read_raw_config())
        self._chats: list[dict[str, Any]] = []
        self._active = 0
        self._next_id = 1
        self._msg_counter = 1
        self._gen = False
        self._compacting = False
        # Событие отмены: прерывает паузы между повторами запроса без опроса.
        self._cancel_event = threading.Event()
        # Предыдущие ответы, которые нужно привязать к новому сообщению ассистента
        # после регенерации (ключ — id чата).
        self._pending_variants: dict[int, list[dict[str, Any]]] = {}
        self._ctx_tokens = 0
        self._post_sink: Any = None
        self._pending_attachments: list[dict[str, Any]] = []
        self._pending_confirm: str | None = None
        # Кэш возможностей моделей OpenRouter (id → поддержка изображений)
        self._or_models_cache: dict[str, bool] = {}
        self._or_vision_started = False
        self._vision_cache: dict[str, tuple[float, dict[str, bool]]] = {}
        # Кэш реальных списков моделей провайдеров (id → (время, список моделей))
        self._api_models_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._or_models_ts = 0.0
        self._load_chats()

    def _t(self: "_ChatEngine", key: str, **params: str) -> str:
        """Локализует строку по ключу словаря I18N_PY с подстановкой параметров."""
        lang = self._config.get("language", "en") if isinstance(self._config, dict) else "en"
        lang = lang if lang in I18N_PY else "en"
        text = I18N_PY[lang].get(key) or I18N_PY["en"].get(key) or key
        for name, value in params.items():
            text = text.replace("{" + name + "}", str(value))
        return text

    def _toast(self: "_ChatEngine", text: str, kind: str = "") -> None:
        """Отправляет в UI всплывающее уведомление."""
        self._post({"type": "toast", "text": text, "kind": kind})

    def _read_raw_config(self: "_ChatEngine") -> dict:
        """Читает и разбирает сырую JSON-конфигурацию capability."""
        try:
            raw = self._cap.get_config()
        except Exception as exc:
            _LOGGER.error(
                "Хост не вернул конфигурацию, используются значения по умолчанию: %s",
                exc,
                exc_info=True,
            )
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _LOGGER.warning("Не удалось разобрать конфигурацию, используются значения по умолчанию")
            return {}
        if not isinstance(data, dict):
            _LOGGER.warning("Конфигурация не является объектом, используются значения по умолчанию")
            return {}
        return data

    def _normalize_config(self: "_ChatEngine", data: dict) -> dict:
        """Приводит произвольный словарь настроек к валидной схеме.

        Мигрирует старую схему (provider/base_url/model/api_key/...), мержит
        с DEFAULT_CONFIG, гарантирует наличие builtin-моделей у встроенных
        провайдеров и сохраняет пользовательские провайдеры и модели.
        """
        if not isinstance(data, dict):
            data = {}
        if "provider" in data and "providers" not in data:
            data = self._migrate_legacy_config(data)
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        # Чистим устаревшие ключи верхнего уровня и фиксируем версию схемы.
        for legacy_key in ("provider", "base_url", "api_key", "model", "scheme"):
            merged.pop(legacy_key, None)
        merged["config_version"] = CONFIG_VERSION
        # Провайдеры: builtin-модели гарантированы, пользовательские сохранены.
        providers = merged.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        normalized_providers: dict[str, dict[str, Any]] = {}
        for pid, pdef in DEFAULT_PROVIDERS.items():
            existing = providers.get(pid)
            if isinstance(existing, dict):
                merged_p = dict(pdef)
                for key, value in existing.items():
                    if key != "models":
                        merged_p[key] = value
                models: dict[str, dict[str, Any]] = {}
                for mid, mdef in pdef.get("models", {}).items():
                    models[mid] = dict(mdef)
                existing_models = existing.get("models")
                if isinstance(existing_models, dict):
                    for mid, mdef in existing_models.items():
                        if isinstance(mdef, dict):
                            models[mid] = dict(mdef)
                merged_p["models"] = models
                normalized_providers[pid] = merged_p
            else:
                normalized_providers[pid] = json.loads(json.dumps(pdef))
        for pid, pdef in providers.items():
            # "custom" — устаревший встроенный псевдо-провайдер: вычищаем его
            # из старых конфигураций (пользовательские провайдеры создаются UI).
            if pid in DEFAULT_PROVIDERS or pid == "custom" or not isinstance(pdef, dict):
                continue
            user_models: dict[str, dict[str, Any]] = {}
            raw_models = pdef.get("models", {})
            if not isinstance(raw_models, dict):
                raw_models = {}
            for mid, mdef in raw_models.items():
                if isinstance(mdef, dict):
                    user_models[mid] = dict(mdef)
            normalized_providers[pid] = {
                "name": str(pdef.get("name", pid)),
                "base_url": str(pdef.get("base_url", "")),
                "api_key": str(pdef.get("api_key", "")),
                "builtin": False,
                "models": user_models,
            }
        merged["providers"] = normalized_providers
        # Per-model настройки и схема API: нормализация для всех провайдеров.
        for pid, pdef in normalized_providers.items():
            pdef["scheme"] = (
                "anthropic" if str(pdef.get("scheme", "openai")) == "anthropic" else "openai"
            )
            for mid, mdef in pdef.get("models", {}).items():
                if not isinstance(mdef, dict):
                    continue
                mdef["temperature"] = normalize_temperature(mdef.get("temperature"))
                mdef["max_tokens"] = normalize_max_tokens(mdef.get("max_tokens"))
                reasoning = mdef.get("reasoning")
                if reasoning is not None:
                    if isinstance(reasoning, str):
                        reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
                    reasoning = bool(reasoning)
                mdef["reasoning"] = reasoning
                # Зрение модели: True/False/None + источник (default/provider/manual).
                vision = mdef.get("vision")
                if vision is not None and not isinstance(vision, bool):
                    if isinstance(vision, str):
                        vision = vision.strip().lower() in ("1", "true", "yes", "on")
                    vision = bool(vision)
                mdef["vision"] = vision
                source = str(mdef.get("vision_source", "default") or "default")
                mdef["vision_source"] = (
                    source if source in ("default", "provider", "manual") else "default"
                )
                # URL, ключ и схема задаются только у провайдера. Убираем
                # легаси-поля моделей из старых конфигураций, чтобы они не
                # перекрывали актуальные креды провайдера.
                for legacy_key in ("base_url", "api_key", "scheme"):
                    mdef.pop(legacy_key, None)
        # Активный провайдер и модель.
        active_provider = str(merged.get("active_provider", "deepseek"))
        if active_provider not in normalized_providers:
            active_provider = "deepseek"
        merged["active_provider"] = active_provider
        prov = normalized_providers.get(active_provider, {})
        models = prov.get("models", {})
        active_model = str(merged.get("active_model", ""))
        if active_model not in models:
            active_model = next(iter(models), "")
        merged["active_model"] = active_model
        # Модель по умолчанию для новых чатов: "provider::model".
        default_model = str(merged.get("default_model", "")).strip()
        if "::" in default_model:
            d_provider, d_model = default_model.split("::", 1)
            d_prov = normalized_providers.get(d_provider)
            if not isinstance(d_prov, dict) or d_model not in d_prov.get("models", {}):
                default_model = ""
        else:
            default_model = ""
        if not default_model:
            default_model = active_provider + "::" + active_model
        merged["default_model"] = default_model
        # Заметки пользователя для контекста.
        merged["notes"] = str(merged.get("notes", ""))
        # Температура: float 0.0–2.0.
        try:
            temperature = float(merged.get("temperature", 0.7))
        except (TypeError, ValueError):
            temperature = 0.7
        if temperature < 0.0 or temperature > 2.0:
            temperature = 0.7
        merged["temperature"] = temperature
        # Максимум токенов: int 1–100000.
        try:
            max_tokens = int(merged.get("max_tokens", 4096))
        except (TypeError, ValueError):
            max_tokens = 4096
        if max_tokens < 1 or max_tokens > 100000:
            max_tokens = 4096
        merged["max_tokens"] = max_tokens
        # Настройки сжатия контекста: вкл/выкл, порог в процентах, окно модели.
        compact_enabled = merged.get("compact_enabled", True)
        if isinstance(compact_enabled, str):
            compact_enabled = compact_enabled.strip().lower() in ("1", "true", "yes", "on")
        merged["compact_enabled"] = bool(compact_enabled)
        try:
            compact_threshold = int(merged.get("compact_threshold", 80))
        except (TypeError, ValueError):
            compact_threshold = 80
        if compact_threshold < 10 or compact_threshold > 100:
            compact_threshold = 80
        merged["compact_threshold"] = compact_threshold
        try:
            context_window = int(merged.get("context_window", 128000))
        except (TypeError, ValueError):
            context_window = 128000
        if context_window < 1000 or context_window > 10_000_000:
            context_window = 128000
        merged["context_window"] = context_window
        # Расширенное мышление: bool.
        reasoning = merged.get("reasoning", False)
        if isinstance(reasoning, str):
            reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
        merged["reasoning"] = bool(reasoning)
        # Оформление.
        if merged.get("theme") not in ("auto", "light", "dark"):
            merged["theme"] = "auto"
        if merged.get("font_style") not in ("system", "mono", "serif"):
            merged["font_style"] = "system"
        # Язык интерфейса: en/ru/sr.
        if merged.get("language") not in ("en", "ru", "sr"):
            merged["language"] = "en"
        # Контекст слайсера: запомненные флаги и режимы выгрузки пресетов.
        # Используются как значения по умолчанию для новых чатов.
        context = merged.get("context")
        if not isinstance(context, dict):
            context = {}
        ctx_flags = context.get("flags")
        ctx_modes = context.get("modes")
        merged["context"] = {
            "flags": dict(ctx_flags) if isinstance(ctx_flags, dict) else {},
            "modes": dict(ctx_modes) if isinstance(ctx_modes, dict) else {},
        }
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

    def _migrate_legacy_config(self: "_ChatEngine", data: dict) -> dict:
        """Преобразует старую схему конфигурации в новую."""
        providers = json.loads(json.dumps(DEFAULT_PROVIDERS))
        provider = str(data.get("provider", "deepseek"))
        if provider not in providers:
            provider = "deepseek"
        if provider == "custom":
            custom_base = str(data.get("custom_base_url", ""))
            custom_model = str(data.get("custom_model", ""))
            providers["custom"]["base_url"] = custom_base
            providers["custom"]["api_key"] = str(data.get("api_key", ""))
            if custom_model:
                providers["custom"]["models"] = {
                    custom_model: {"name": custom_model, "builtin": False}
                }
            active_provider = "custom"
            active_model = custom_model
        else:
            providers[provider]["api_key"] = str(data.get("api_key", ""))
            active_provider = provider
            active_model = str(data.get("model", ""))
        return {
            "providers": providers,
            "active_provider": active_provider,
            "active_model": active_model,
            "default_model": active_provider + "::" + active_model,
            "notes": "",
            "theme": data.get("theme", "auto"),
            "font_size": data.get("font_size", 14),
            "font_style": data.get("font_style", "system"),
            "language": "en",
            "usage": data.get("usage", {}),
        }

    def _sync_config(self: "_ChatEngine") -> None:
        """Перечитывает конфигурацию из capability и обновляет память.

        Не пишет на диск: правки, внесённые в настройках слайсера, должны
        остаться нетронутыми, а память — синхронизированной с ними.
        """
        with self._persist_lock:
            try:
                raw = self._read_raw_config()
            except Exception as exc:
                _LOGGER.error("Не удалось перечитать конфигурацию: %s", exc)
                return
            self._config = self._normalize_config(raw)

    def load_config(self: "_ChatEngine") -> dict:
        """Возвращает копию текущей конфигурации."""
        return dict(self._config)

    def save_config(self: "_ChatEngine", config: dict) -> bool:
        """Нормализует и сохраняет конфигурацию через capability."""
        self._config = self._normalize_config(config)
        with self._persist_lock:
            return self._persist_config_locked()

    def _persist_config(self: "_ChatEngine") -> bool:
        """Сохраняет текущую конфигурацию через capability.

        Единая точка записи: любые ошибки хоста (включая запрет аудита)
        логируются и не приводят к падению обработчика.
        """
        with self._persist_lock:
            return self._persist_config_locked()

    def _persist_config_locked(self: "_ChatEngine") -> bool:
        """Сохраняет конфигурацию; вызывается при уже взятом _persist_lock."""
        try:
            raw = json.dumps(self._config)
        except (TypeError, ValueError) as exc:
            _LOGGER.error("Не удалось сериализовать конфигурацию: %s", exc, exc_info=True)
            return False
        try:
            return bool(self._cap.save_config(raw))
        except Exception as exc:
            _LOGGER.error("Не удалось сохранить конфигурацию: %s", exc, exc_info=True)
            return False

    def reset_config(self: "_ChatEngine") -> dict:
        """Сбрасывает конфигурацию к значениям по умолчанию."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._persist_config()
        return dict(self._config)

    def set_post_sink(self: "_ChatEngine", sink: Any) -> None:
        """Устанавливает callable для доставки payload в UI."""
        self._post_sink = sink

    # ===== Персист истории чатов =====

    def _load_chats(self: "_ChatEngine") -> None:
        """Загружает историю чатов из файла, при ошибке создаёт пустое состояние."""
        data: dict[str, Any] = {}
        try:
            raw = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Не удалось загрузить историю чатов: %s", exc)
        chats = data.get("chats", [])
        self._chats = [c for c in chats if isinstance(c, dict)] if isinstance(chats, list) else []
        # Миграция: пустой заголовок — маркер нового чата (JS подставляет
        # локализованный common.new_chat), старый русский маркер нормализуем.
        for chat in self._chats:
            if chat.get("title") == "Новый чат":
                chat["title"] = ""
            # Миграция: у старых чатов может не быть флагов и режимов
            # выгрузки контекста — восстанавливаем значения по умолчанию.
            if not isinstance(chat.get("context_flags"), dict):
                chat["context_flags"] = {key: True for key in CONTEXT_OPTIONS}
            if not isinstance(chat.get("context_modes"), dict):
                chat["context_modes"] = {
                    key: "changed" for key in PRESET_CONTEXT_KEYS
                }
            if not isinstance(chat.get("msgs"), list):
                chat["msgs"] = []
            # Миграция: старые версии дописывали метки вложений прямо в текст.
            for msg in chat["msgs"]:
                if isinstance(msg, dict) and isinstance(msg.get("text"), str):
                    msg["text"] = self._strip_legacy_markers(msg["text"])
        self._active = self._as_int(data.get("active"), 0)
        self._next_id = self._as_int(data.get("next_id"), 1)
        self._msg_counter = self._as_int(data.get("next_msg_id"), 1)
        if not self._chats:
            self._create_chat()
        # Пересчитываем токены активного чата: после перезапуска счётчик сбрасывался.
        active_chat = self._active_chat()
        self._ctx_tokens = self._estimate_context_tokens(
            active_chat.get("context_flags", {}), active_chat.get("context_modes", {})
        )

    @staticmethod
    def _strip_legacy_markers(text: str) -> str:
        """Убирает легаси-метки вложений, которые старые версии дописывали в текст.

        Метка вида ``[file: name]`` больше не добавляется: содержимое вложений
        хранится в самом сообщении, поэтому такая метка только путает модель.
        """
        for marker in (" [photo]", " [фото]", " [foto]"):
            text = text.replace(marker, "")
        for prefix in ("[file: ", "[файл: ", "[fajl: "):
            while True:
                start = text.rfind(prefix)
                if start == -1:
                    break
                end = text.find("]", start)
                if end == -1:
                    break
                text = text[:start].rstrip() + text[end + 1:]
        return text

    def _flatten_chats(self: "_ChatEngine") -> list[dict[str, Any]]:
        """Возвращает копию чатов для записи на диск и отправки в UI.

        Текст вложений сохраняется (с ограничением), чтобы содержимое файлов
        не терялось при перезапуске движка. Тяжёлые изображения (data URI) не
        пишутся: вместо них остаётся пометка с именем.
        """
        result: list[dict[str, Any]] = []
        for chat in self._chats:
            if not isinstance(chat, dict):
                continue
            flat_msgs: list[dict[str, Any]] = []
            raw_msgs = chat.get("msgs", [])
            if not isinstance(raw_msgs, list):
                raw_msgs = []
            for msg in raw_msgs:
                if not isinstance(msg, dict):
                    continue
                flat = dict(msg)
                if flat.get("image"):
                    flat.pop("image", None)
                    flat["attachments"] = self._merge_attachment(
                        flat.get("attachments"),
                        {"kind": "image", "name": self._t("attach.photo_name")},
                    )
                file_info = flat.get("file")
                if isinstance(file_info, dict):
                    content = str(file_info.get("text", ""))
                    flat["file"] = {
                        "name": str(file_info.get("name", "")),
                        "text": content[:MAX_PERSISTED_FILE_CHARS],
                        "truncated": len(content) > MAX_PERSISTED_FILE_CHARS,
                    }
                attachments = flat.get("attachments")
                if isinstance(attachments, list):
                    flat["attachments"] = self._flatten_attachments(attachments)
                flat_msgs.append(flat)
            flat_chat = dict(chat)
            flat_chat["msgs"] = flat_msgs
            result.append(flat_chat)
        return result

    def _flatten_attachments(self, attachments: list) -> list[dict[str, Any]]:
        """Готовит вложения к записи на диск.

        Текст файлов сохраняется с ограничением, изображения — только именем.
        """
        cleaned: list[dict[str, Any]] = []
        for att in attachments:
            if not isinstance(att, dict):
                continue
            if att.get("image"):
                cleaned.append(
                    {"kind": "image", "name": str(att.get("name", ""))}
                )
            elif isinstance(att.get("file"), dict):
                file_info = att["file"]
                content = str(file_info.get("text", ""))
                cleaned.append(
                    {
                        "kind": "text",
                        "file": {
                            "name": str(file_info.get("name", "")),
                            "text": content[:MAX_PERSISTED_FILE_CHARS],
                            "truncated": len(content) > MAX_PERSISTED_FILE_CHARS,
                        },
                    }
                )
        return cleaned

    @staticmethod
    def _merge_attachment(attachments: Any, item: dict[str, Any]) -> list[dict[str, Any]]:
        """Добавляет пометку вложения к существующему списку или создаёт его."""
        result = [att for att in attachments if isinstance(att, dict)] if isinstance(
            attachments, list
        ) else []
        result.append(item)
        return result

    def _save_chats(self: "_ChatEngine") -> None:
        """Сохраняет историю чатов в файл под блокировкой без тяжёлых вложений."""
        with self._persist_lock:
            try:
                payload = {
                    "chats": self._flatten_chats(),
                    "active": self._active,
                    "next_id": self._next_id,
                    "next_msg_id": self._msg_counter,
                }
                atomic_write_text(
                    CHATS_FILE, json.dumps(payload, ensure_ascii=False)
                )
            except (OSError, TypeError, ValueError) as exc:
                _LOGGER.error(
                    "Не удалось сохранить историю чатов: %s", exc, exc_info=True
                )

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        """Приводит значение к целому числу с запасным значением."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ===== Мультичат =====

    def _create_chat(self: "_ChatEngine") -> dict[str, Any]:
        """Создаёт новый чат и делает его активным.

        Флаги контекста и режимы выгрузки пресетов наследуются от последних
        использованных (хранятся в конфигурации), чтобы не выставлять их заново.
        """
        saved = self._config.get("context")
        saved = saved if isinstance(saved, dict) else {}
        saved_flags = saved.get("flags")
        saved_flags = saved_flags if isinstance(saved_flags, dict) else {}
        saved_modes = saved.get("modes")
        saved_modes = saved_modes if isinstance(saved_modes, dict) else {}
        flags = {key: bool(saved_flags.get(key, True)) for key in CONTEXT_OPTIONS}
        modes = {
            key: ("all" if saved_modes.get(key) == "all" else "changed")
            for key in PRESET_CONTEXT_KEYS
        }
        chat = {
            "id": self._next_id,
            "title": "",
            "updated": time.time(),
            "pinned": False,
            "context_flags": flags,
            "context_modes": modes,
            "msgs": [],
        }
        self._next_id += 1
        self._chats.append(chat)
        self._active = chat["id"]
        self._ctx_tokens = self._estimate_context_tokens(flags, modes)
        # Новый чат стартует на модели по умолчанию (конфиг уже нормализован).
        default_model = str(self._config.get("default_model", ""))
        if "::" in default_model:
            d_provider, d_model = default_model.split("::", 1)
            providers = self._config.get("providers", {})
            if d_provider in providers and d_model in providers[d_provider].get("models", {}):
                if (
                    self._config.get("active_provider") != d_provider
                    or self._config.get("active_model") != d_model
                ):
                    self._config["active_provider"] = d_provider
                    self._config["active_model"] = d_model
                    self._persist_config()
        self._save_chats()
        return chat

    def _chat_by_id(self: "_ChatEngine", chat_id: Any) -> dict[str, Any] | None:
        """Возвращает чат по идентификатору либо None."""
        for chat in self._chats:
            if chat.get("id") == chat_id:
                return chat
        return None

    def _active_chat(self: "_ChatEngine") -> dict[str, Any]:
        """Возвращает активный чат, создавая его при необходимости."""
        chat = self._chat_by_id(self._active)
        if chat is None:
            chat = self._create_chat()
        return chat

    def _next_msg_id(self: "_ChatEngine") -> int:
        """Возвращает следующий идентификатор сообщения и инкрементирует счётчик."""
        msg_id = self._msg_counter
        self._msg_counter += 1
        return msg_id

    def _trim_chat(self: "_ChatEngine", chat: dict[str, Any]) -> None:
        """Обрезает историю чата до максимального числа сообщений."""
        msgs = chat.get("msgs", [])
        if len(msgs) > MAX_CHAT_MESSAGES:
            del msgs[: len(msgs) - MAX_CHAT_MESSAGES]

    def _auto_title(self: "_ChatEngine", text: str) -> str:
        """Формирует заголовок чата из первого сообщения."""
        return " ".join(text.split())[:40]

    def _append_assistant(self: "_ChatEngine", text: str) -> None:
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

    def _append_system(self: "_ChatEngine", text: str) -> None:
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

    def _settings_snapshot(self: "_ChatEngine") -> dict[str, Any]:
        """Возвращает настройки для UI без секретов.

        API-ключ не покидает движок: в UI передаётся только признак его
        наличия, чтобы форма могла показать placeholder «ключ задан».
        """
        settings = {key: self._config[key] for key in SETTINGS_KEYS}
        provider_id = str(self._config.get("active_provider", "deepseek"))
        providers = self._config.get("providers", {})
        prov = providers.get(provider_id)
        settings["has_api_key"] = bool(
            isinstance(prov, dict) and str(prov.get("api_key", "")).strip()
        )
        return settings

    def _send_state(self: "_ChatEngine", include_images: bool = False) -> None:
        """Формирует и отправляет снимок состояния в UI.

        По умолчанию изображения (data URI) не передаются: они тяжёлые, а UI
        хранит их локально и сам восстанавливает по идентификатору сообщения.
        Полный снимок с изображениями запрашивается только при загрузке,
        переключении чата и старте генерации.
        """
        chat = self._active_chat()
        chats = self._chats if include_images else self._flatten_chats()
        self._post(
            {
                "type": "state",
                "chats": chats,
                "active": self._active,
                "settings": self._settings_snapshot(),
                "providers": self._providers_snapshot(),
                "commands": [
                    {"cmd": cmd, "desc": self._t("cmd." + cmd.lstrip("/") + ".desc")}
                    for cmd, _desc in COMMANDS
                ],
                "context_flags": chat["context_flags"],
                "context_modes": chat.get("context_modes", {}),
                "context_tokens": self._ctx_tokens,
                "status": "streaming" if self._gen else "",
            }
        )

    def _providers_snapshot(self: "_ChatEngine") -> list[dict[str, Any]]:
        """Возвращает список провайдеров для UI без секретов.

        API-ключи (провайдеров и моделей) в webview не передаются: вместо них
        отдаётся булев признак ``has_key``. Так форма знает, что ключ задан,
        но сам секрет остаётся только в памяти движка и конфиге Orca.
        """
        result: list[dict[str, Any]] = []
        providers = self._config.get("providers", {})
        # Карта модальностей: если кэша нет, уточняем в фоне только при
        # активном UI — иначе (например, в тестах) сеть не трогаем.
        or_map = self._or_models_cache
        vision_caches = self._vision_cache
        # Фоновое уточнение запускаем ровно один раз, под блокировкой.
        with self._vision_lock:
            start_vision = not self._or_vision_started and self._post_sink is not None
            if start_vision:
                self._or_vision_started = True
        if start_vision:
            threading.Thread(target=self._refresh_all_vision, daemon=True).start()
        for pid, pdef in providers.items():
            if not isinstance(pdef, dict):
                continue
            models: list[dict[str, Any]] = []
            raw_models = pdef.get("models", {})
            if not isinstance(raw_models, dict):
                raw_models = {}
            for mid, mdef in raw_models.items():
                if isinstance(mdef, dict):
                    vision = mdef.get("vision")
                    vision_source = str(mdef.get("vision_source", "default"))
                    if vision_source != "manual":
                        cached_map = (
                            or_map
                            if pid == "openrouter"
                            else vision_caches.get(pid, (0.0, {}))[1]
                        )
                        if mid in cached_map:
                            vision = cached_map[mid]
                            vision_source = "provider"
                    entry: dict[str, Any] = {
                        "id": mid,
                        "name": str(mdef.get("name", mid)),
                        "builtin": bool(mdef.get("builtin", False)),
                        "temperature": mdef.get("temperature"),
                        "max_tokens": mdef.get("max_tokens"),
                        "reasoning": mdef.get("reasoning"),
                        "vision": vision,
                        "vision_source": vision_source,
                        "price_in": mdef.get("price_in"),
                        "price_out": mdef.get("price_out"),
                    }
                    models.append(entry)
            prov_entry: dict[str, Any] = {
                "id": pid,
                "name": str(pdef.get("name", pid)),
                "builtin": bool(pdef.get("builtin", False)),
                "scheme": str(pdef.get("scheme", "openai")),
                "has_key": bool(str(pdef.get("api_key", "")).strip()),
                "models": models,
            }
            if not pdef.get("builtin", False):
                prov_entry["base_url"] = str(pdef.get("base_url", ""))
            result.append(prov_entry)
        return result

    def _net_active(self: "_ChatEngine") -> bool:
        """Возвращает True, пока сетевой запрос разрешён (генерация или сжатие).

        Используется ретраями и блокирующими запросами: кнопка «Стоп»
        переводит оба флага в False, прерывая ожидание и повторы.
        """
        return bool(self._gen or self._compacting)

    def _post(self: "_ChatEngine", payload: dict) -> None:
        """Отправляет payload в UI через установленный sink."""
        sink = self._post_sink
        if sink is None:
            return
        try:
            sink(payload)
        except Exception as exc:
            _LOGGER.error("Не удалось отправить payload в UI: %s", exc)
