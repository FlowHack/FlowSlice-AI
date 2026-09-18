# pyright: ignore[reportGeneralTypeIssues]
"""Диспетчер UI-сообщений движка FlowSlice AI.

Миксин HandlersMixin разбирает входящие сообщения из webview и направляет
их в соответствующие хендлеры: чат, управление чатами, настройки, вложения.
"""
# pylint: disable=too-many-lines,too-many-branches,too-many-statements
# pylint: disable=too-many-public-methods,too-many-nested-blocks,too-few-public-methods

import json
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.config import DEFAULT_CONFIG
from flowslice_ai.constants import MAX_FILE_CHARS, MAX_IMAGE_B64
from flowslice_ai.logging import _LOGGER


class HandlersMixin:
    """Обработчики сообщений из UI и вспомогательные методы состояния."""

    def handle_message(self: "_ChatEngine", message: dict) -> None:
        """Разбирает входящее сообщение из UI и направляет в соответствующий хендлер."""
        self._sync_config()
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
            self._handle_test_key(message)
        elif msg_type == "get_usage":
            self._handle_get_usage(message)
        elif msg_type == "attach_file":
            self._handle_attach_file(message)
        elif msg_type == "set_model":
            self._handle_set_model(message)
        elif msg_type == "set_default_model":
            self._handle_set_default_model(message)
        elif msg_type == "add_provider":
            self._handle_add_provider(message)
        elif msg_type == "update_provider":
            self._handle_update_provider(message)
        elif msg_type == "delete_provider":
            self._handle_delete_provider(message)
        elif msg_type == "add_model":
            self._handle_add_model(message)
        elif msg_type == "update_model":
            self._handle_update_model(message)
        elif msg_type == "delete_model":
            self._handle_delete_model(message)
        else:
            _LOGGER.warning("Неизвестный тип сообщения из UI: %s", msg_type)

    # ===== Хендлеры =====

    def _handle_get_state(self: "_ChatEngine") -> None:
        """Отправляет полное состояние интерфейса."""
        self._send_state()

    def _handle_chat(self: "_ChatEngine", message: dict) -> None:
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
                    "text": self._t("gen.already"),
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
        if not chat["title"]:
            chat["title"] = self._auto_title(text)
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        self._start_generation(chat["id"], text, user_msg["id"])

    def _apply_edit(self: "_ChatEngine", chat: dict[str, Any], edit_id: Any, text: str) -> None:
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

    def _handle_new_chat(self: "_ChatEngine") -> None:
        """Создаёт новый чат и обновляет интерфейс."""
        self._create_chat()
        self._send_state()

    def _handle_pick_chat(self: "_ChatEngine", message: dict) -> None:
        """Переключает активный чат по идентификатору."""
        chat_id = message.get("id")
        if self._chat_by_id(chat_id) is not None:
            self._active = chat_id
            self._send_state()

    def _handle_delete_chat(self: "_ChatEngine", message: dict) -> None:
        """Удаляет чат и корректирует активный идентификатор."""
        chat_id = message.get("id")
        self._chats = [chat for chat in self._chats if chat.get("id") != chat_id]
        if self._active == chat_id:
            self._active = self._chats[0]["id"] if self._chats else 0
        if not self._chats:
            self._create_chat()
        self._save_chats()
        self._send_state()

    def _handle_rename_chat(self: "_ChatEngine", message: dict) -> None:
        """Переименовывает чат по идентификатору."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        title = str(message.get("title", "")).strip()[:60]
        chat["title"] = title
        self._save_chats()
        self._send_state()

    def _handle_toggle_pin(self: "_ChatEngine", message: dict) -> None:
        """Переключает закрепление чата."""
        chat = self._chat_by_id(message.get("id"))
        if chat is None:
            return
        chat["pinned"] = not chat.get("pinned", False)
        self._save_chats()
        self._send_state()

    def _handle_stop(self: "_ChatEngine") -> None:
        """Останавливает текущую генерацию."""
        self._gen = False
        self._post({"type": "status", "text": ""})

    def _handle_context_flags(self: "_ChatEngine", message: dict) -> None:
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

    def _handle_regenerate(self: "_ChatEngine") -> None:
        """Перегенерирует последний ответ ассистента."""
        if self._gen:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("gen.already"),
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

    def _handle_save_settings(self: "_ChatEngine", message: dict) -> None:
        """Сохраняет настройки, присланные из UI.

        Принимает новую схему (active_provider/active_model/api_key/...) и
        старую (provider/model/custom_*) для обратной совместимости с текущим JS.
        """
        settings = message.get("settings", {})
        if not isinstance(settings, dict):
            return
        for key in (
            "active_provider",
            "active_model",
            "default_model",
            "notes",
            "temperature",
            "max_tokens",
            "reasoning",
            "theme",
            "font_size",
            "font_style",
            "language",
        ):
            if key in settings:
                self._config[key] = settings[key]
        # Обратная совместимость со старой схемой из текущего JS.
        if "provider" in settings:
            self._config["active_provider"] = settings["provider"]
        if "model" in settings:
            self._config["active_model"] = settings["model"]
        if settings.get("custom_model"):
            self._config["active_model"] = settings["custom_model"]
        if "custom_base_url" in settings:
            providers = self._config.setdefault("providers", {})
            providers.setdefault("custom", {})["base_url"] = settings["custom_base_url"]
        if "api_key" in settings:
            provider_id = str(self._config.get("active_provider", "deepseek"))
            providers = self._config.setdefault("providers", {})
            providers.setdefault(provider_id, {})["api_key"] = str(settings["api_key"])
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": self._t("settings.saved"), "kind": "ok"})

    def _handle_reset_settings(self: "_ChatEngine") -> None:
        """Сбрасывает настройки к заводским значениям."""
        self._config = self._normalize_config(DEFAULT_CONFIG.copy())
        self._cap.save_config(json.dumps(self._config))
        self._post_settings()
        self._post({"type": "toast", "text": self._t("settings.reset"), "kind": "ok"})

    def _post_settings(self: "_ChatEngine") -> None:
        """Отправляет актуальные настройки в UI."""
        self._post(
            {
                "type": "settings",
                "settings": self._settings_snapshot(),
            }
        )

    def _handle_test_key(self: "_ChatEngine", message: dict) -> None:
        """Запускает проверку API-ключа в фоновом потоке.

        Если в сообщении передан ключ (поле "key"), проверяется именно он,
        иначе — ключ активного провайдера.
        """
        key = message.get("key")
        if not isinstance(key, str) or not key.strip():
            key = None
        threading.Thread(target=self._test_key_worker, args=(key,), daemon=True).start()

    def _handle_get_usage(self: "_ChatEngine", message: dict) -> None:
        """Отправляет статистику использования за выбранный период."""
        period = message.get("period", "all")
        snap = self._usage_snapshot(period)
        self._post({"type": "usage", **snap})

    def _handle_attach_file(self: "_ChatEngine", message: dict) -> None:
        """Сохраняет вложение для следующего сообщения."""
        kind = message.get("kind")
        name = str(message.get("name", self._t("attach.default_name")))
        data = message.get("data", "")
        if kind == "image":
            if len(data) > MAX_IMAGE_B64:
                self._post(
                    {
                        "type": "toast",
                        "text": self._t("attach.image_too_big"),
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
                        "text": self._t("attach.file_too_big"),
                        "kind": "err",
                    }
                )
                return
            self._pending_attachment = {"file": {"name": name, "text": data}}
        self._post({"type": "toast", "text": self._t("attach.added"), "kind": "ok"})
