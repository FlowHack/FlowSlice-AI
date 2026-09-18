"""Диспетчер UI-сообщений движка FlowSlice AI.

Миксин HandlersMixin разбирает входящие сообщения из webview и направляет
их в соответствующие хендлеры: чат, управление чатами, настройки, вложения.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-branches,too-many-statements
# pylint: disable=too-many-public-methods,too-many-nested-blocks,too-few-public-methods

import json
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

from flowslice_ai.config import DEFAULT_CONFIG, RESET_SCOPES, SETTINGS_KEYS
from flowslice_ai.constants import (
    MAX_ATTACHMENTS,
    MAX_FILE_CHARS,
    MAX_IMAGE_B64,
    MAX_TOTAL_FILE_CHARS,
    MAX_TOTAL_IMAGE_B64,
    PRESET_CONTEXT_KEYS,
)
from flowslice_ai.logging import _LOGGER
from flowslice_ai.providers_data import DEFAULT_PROVIDERS


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
        elif msg_type == "clear_chats":
            self._handle_clear_chats()
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
            self._handle_reset_settings(message)
        elif msg_type == "reset_models":
            self._handle_reset_models()
        elif msg_type == "reset_custom_models":
            self._handle_reset_custom_models()
        elif msg_type == "test_key":
            self._handle_test_key(message)
        elif msg_type == "get_usage":
            self._handle_get_usage(message)
        elif msg_type == "attach_file":
            self._handle_attach_file(message)
        elif msg_type == "set_model":
            self._handle_set_model(message)
        elif msg_type == "set_api_model":
            self._handle_set_api_model(message)
        elif msg_type == "import_api_model":
            self._handle_import_api_model(message)
        elif msg_type == "refresh_models":
            self._handle_refresh_models(message)
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
        # Вложения могут прийти вместе с сообщением (основной канал).
        incoming = message.get("attachments")
        if incoming:
            self._accept_attachments(incoming)
        if not text and not self._pending_attachments:
            return
        # Заголовок чата для отправки одним вложением формируем по его метке,
        # но сам текст сообщения не подменяем: пользователь его не писал.
        title_text = text or self._attachment_label()
        if text.startswith("/"):
            if self._handle_command(text):
                self._pending_attachments = []
                return
            # Неизвестную команду не отправляем в модель.
            self._post(
                {
                    "type": "toast",
                    "text": self._t("cmd.unknown", cmd=text.strip().split()[0]),
                    "kind": "err",
                }
            )
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
        # Модель могла смениться уже после прикрепления изображения.
        if any(att.get("image") for att in self._pending_attachments) and (
            self._model_supports_images() is False
        ):
            self._pending_attachments = []
            self._post(
                {
                    "type": "toast",
                    "text": self._t(
                        "attach.image_unsupported", model=self._active_model_id()
                    ),
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
        if self._pending_attachments:
            user_msg["attachments"] = self._pending_attachments
            self._pending_attachments = []
        chat["msgs"].append(user_msg)
        if not chat["title"]:
            chat["title"] = self._auto_title(title_text)
        chat["updated"] = time.time()
        self._trim_chat(chat)
        self._save_chats()
        # Показываем отправленное сообщение в UI до старта стриминга.
        self._send_state()
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
                self._send_state()
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
            chat = self._active_chat()
            self._ctx_tokens = self._estimate_context_tokens(
                chat.get("context_flags", {}), chat.get("context_modes", {})
            )
            self._save_chats()
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

    def _handle_clear_chats(self: "_ChatEngine") -> None:
        """Удаляет всю историю чатов и создаёт новый пустой чат."""
        self._chats = []
        self._active = 0
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
        with self._gen_lock:
            self._gen = False
        self._post({"type": "status", "text": ""})

    def _handle_context_flags(self: "_ChatEngine", message: dict) -> None:
        """Обновляет флаги и режимы контекста активного чата.

        Дополнительно запоминает выбор в конфигурации, чтобы новые чаты
        наследовали его без повторной настройки.
        """
        flags = message.get("flags", {})
        if not isinstance(flags, dict):
            return
        chat = self._active_chat()
        chat["context_flags"] = {
            key: bool(flags.get(key, value))
            for key, value in chat["context_flags"].items()
        }
        modes = message.get("modes")
        current_modes = chat.get("context_modes")
        if not isinstance(current_modes, dict):
            current_modes = {}
        if isinstance(modes, dict):
            for key in PRESET_CONTEXT_KEYS:
                current_modes[key] = "all" if modes.get(key) == "all" else "changed"
        chat["context_modes"] = {
            key: ("all" if current_modes.get(key) == "all" else "changed")
            for key in PRESET_CONTEXT_KEYS
        }
        self._ctx_tokens = self._estimate_context_tokens(
            chat["context_flags"], chat["context_modes"]
        )
        self._save_chats()
        self._remember_context(chat)
        self._send_state()

    def _remember_context(self: "_ChatEngine", chat: dict[str, Any]) -> None:
        """Сохраняет флаги и режимы контекста как значения по умолчанию."""
        self._config["context"] = {
            "flags": dict(chat.get("context_flags", {})),
            "modes": dict(chat.get("context_modes", {})),
        }
        self._persist_config()

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
        for key in SETTINGS_KEYS:
            if key in settings:
                self._config[key] = settings[key]
        # Обратная совместимость со старой схемой из текущего JS.
        if "provider" in settings:
            self._config["active_provider"] = settings["provider"]
        if "model" in settings:
            self._config["active_model"] = settings["model"]
        if "api_key" in settings:
            api_key = settings["api_key"]
            # Пустое поле означает «не менять ключ»: в UI ключ не предзаполняется.
            if isinstance(api_key, str) and api_key.strip():
                provider_id = str(self._config.get("active_provider", "deepseek"))
                providers = self._config.setdefault("providers", {})
                providers.setdefault(provider_id, {})["api_key"] = api_key.strip()
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._post_settings()
        # Обновляем снимок провайдеров: после сохранения ключа список моделей
        # в UI должен сразу увидеть has_key, иначе он остаётся пустым.
        self._send_state()
        self._post({"type": "toast", "text": self._t("settings.saved"), "kind": "ok"})
        # Ключ мог появиться в текущей сессии: уточняем зрение в фоне.
        self._schedule_vision_refresh()

    def _handle_reset_settings(self: "_ChatEngine", message: dict) -> None:
        """Сбрасывает к заводским значениям только ключи текущей вкладки настроек."""
        scope = str(message.get("scope", ""))
        keys = RESET_SCOPES.get(scope)
        if not keys:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("settings.reset_scope_unknown"),
                    "kind": "err",
                }
            )
            return
        for key in keys:
            if key in DEFAULT_CONFIG:
                self._config[key] = json.loads(json.dumps(DEFAULT_CONFIG[key]))
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._post_settings()
        self._post({"type": "toast", "text": self._t("settings.reset"), "kind": "ok"})

    def _handle_reset_models(self: "_ChatEngine") -> None:
        """Сбрасывает встроенные провайдеры и их модели к заводским значениям.

        Вместе с моделями очищаются и сохранённые API-ключи: после сброса
        список моделей чата пуст, пока пользователь не укажет токен заново.
        """
        providers = self._config.setdefault("providers", {})
        for pid, pdef in DEFAULT_PROVIDERS.items():
            providers[pid] = json.loads(json.dumps(pdef))
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post({"type": "toast", "text": self._t("settings.models_reset"), "kind": "ok"})
        self._schedule_vision_refresh()

    def _handle_reset_custom_models(self: "_ChatEngine") -> None:
        """Удаляет всех пользовательских провайдеров и их модели."""
        providers = self._config.get("providers", {})
        for pid in [
            p
            for p, d in providers.items()
            if isinstance(d, dict) and not d.get("builtin")
        ]:
            del providers[pid]
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("settings.custom_models_reset"), "kind": "ok"}
        )

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
        provider_id = message.get("provider")
        if not isinstance(provider_id, str) or not provider_id.strip():
            provider_id = None
        threading.Thread(
            target=self._test_key_worker, args=(key, provider_id), daemon=True
        ).start()

    def _handle_get_usage(self: "_ChatEngine", message: dict) -> None:
        """Отправляет статистику использования за выбранный период."""
        period = message.get("period", "all")
        snap = self._usage_snapshot(period)
        self._post({"type": "usage", **snap})

    def _checked_attachment(
        self: "_ChatEngine", kind: Any, name: str, data: Any
    ) -> dict[str, Any] | None:
        """Проверяет вложение и возвращает нормализованное представление."""
        if not isinstance(data, str) or not data:
            _LOGGER.warning("Пропущено вложение без данных (kind=%s)", kind)
            return None
        if kind == "image":
            # Модель без зрения: изображение отклонить с понятным пояснением.
            if self._model_supports_images() is False:
                self._post(
                    {
                        "type": "toast",
                        "text": self._t(
                            "attach.image_unsupported",
                            model=self._active_model_id(),
                        ),
                        "kind": "err",
                    }
                )
                return None
            if len(data) > MAX_IMAGE_B64:
                self._post(
                    {
                        "type": "toast",
                        "text": self._t("attach.image_too_big"),
                        "kind": "err",
                    }
                )
                return None
            return {"image": data, "name": name}
        if len(data) > MAX_FILE_CHARS:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("attach.file_too_big"),
                    "kind": "err",
                }
            )
            return None
        return {"file": {"name": name, "text": data}}

    def _attachment_label(self: "_ChatEngine") -> str:
        """Возвращает метку для сообщения, отправленного только вложением."""
        if not self._pending_attachments:
            return ""
        first = self._pending_attachments[0]
        if first.get("image"):
            return self._t("chat.photo_marker").strip()
        name = str(first.get("file", {}).get("name", ""))
        return self._t("chat.file_marker", name=name).strip()

    def _attachment_totals(self: "_ChatEngine") -> tuple[int, int]:
        """Считает суммарные объёмы ожидающих вложений (текст, изображения)."""
        text_chars = 0
        image_b64 = 0
        for att in self._pending_attachments:
            if att.get("image"):
                image_b64 += len(str(att["image"]))
            elif att.get("file"):
                text_chars += len(str(att["file"].get("text", "")))
        return text_chars, image_b64

    def _accept_attachments(self: "_ChatEngine", items: Any) -> int:
        """Добавляет валидные вложения из списка и возвращает число принятых."""
        if not isinstance(items, list):
            return 0
        accepted = 0
        text_chars, image_b64 = self._attachment_totals()
        for item in items:
            if not isinstance(item, dict):
                continue
            if len(self._pending_attachments) >= MAX_ATTACHMENTS:
                self._post(
                    {
                        "type": "toast",
                        "text": self._t("attach.limit_count", n=str(MAX_ATTACHMENTS)),
                        "kind": "err",
                    }
                )
                break
            att = self._checked_attachment(
                item.get("kind"),
                str(item.get("name", self._t("attach.default_name"))),
                item.get("data", ""),
            )
            if att is None:
                continue
            if att.get("image"):
                if image_b64 + len(str(att["image"])) > MAX_TOTAL_IMAGE_B64:
                    self._post(
                        {
                            "type": "toast",
                            "text": self._t("attach.images_total_too_big"),
                            "kind": "err",
                        }
                    )
                    continue
                image_b64 += len(str(att["image"]))
            else:
                size = len(str(att["file"].get("text", "")))
                if text_chars + size > MAX_TOTAL_FILE_CHARS:
                    self._post(
                        {
                            "type": "toast",
                            "text": self._t("attach.files_total_too_big"),
                            "kind": "err",
                        }
                    )
                    continue
                text_chars += size
            self._pending_attachments.append(att)
            accepted += 1
        return accepted

    def _handle_attach_file(self: "_ChatEngine", message: dict) -> None:
        """Сохраняет вложение для следующего сообщения (legacy-путь).

        Основной канал — поле ``attachments`` в сообщении ``chat``; этот
        обработчик оставлен для совместимости.
        """
        if self._accept_attachments([message]):
            self._post({"type": "toast", "text": self._t("attach.added"), "kind": "ok"})
