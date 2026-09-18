# pyright: ignore[reportGeneralTypeIssues]
"""Управление провайдерами и моделями движка FlowSlice AI.

Миксин ProvidersMixin реализует CRUD-операции над провайдерами и моделями:
выбор активной модели, добавление/обновление/удаление пользовательских
провайдеров и моделей, генерация слагов и случайных суффиксов.
"""
# pylint: disable=too-many-lines,too-many-statements,too-many-branches
# pylint: disable=too-many-locals,too-many-public-methods,too-few-public-methods,line-too-long

import json
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine


class ProvidersMixin:
    """CRUD провайдеров и моделей, выбор активной модели."""

    def _handle_set_model(self: "_ChatEngine", message: dict) -> None:
        """Устанавливает активного провайдера и модель."""
        provider = str(message.get("provider", ""))
        model = str(message.get("model", ""))
        providers = self._config.get("providers", {})
        if provider not in providers:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("provider.not_found_name", name=provider),
                    "kind": "err",
                }
            )
            return
        if model not in providers[provider].get("models", {}):
            self._post(
                {
                    "type": "toast",
                    "text": self._t("model.not_found_name", name=model),
                    "kind": "err",
                }
            )
            return
        self._config["active_provider"] = provider
        self._config["active_model"] = model
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": self._t("model.selected", name=model), "kind": "ok"})

    def _handle_set_default_model(self: "_ChatEngine", message: dict) -> None:
        """Устанавливает модель по умолчанию для новых чатов."""
        provider = str(message.get("provider", ""))
        model = str(message.get("model", ""))
        providers = self._config.get("providers", {})
        if provider not in providers or model not in providers[provider].get("models", {}):
            self._post({"type": "toast", "text": self._t("model.not_found"), "kind": "err"})
            return
        self._config["default_model"] = provider + "::" + model
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.default_set", name=model), "kind": "ok"}
        )

    def _handle_add_provider(self: "_ChatEngine", message: dict) -> None:
        """Создаёт пользовательского провайдера."""
        name = str(message.get("name", "")).strip()
        if not name:
            self._post(
                {"type": "toast", "text": self._t("provider.name_required"), "kind": "err"}
            )
            return
        base_url = str(message.get("base_url", "")).strip()
        api_key = str(message.get("api_key", "")).strip()
        pid = self._slugify(name) + "_" + self._random_suffix()
        providers = self._config.setdefault("providers", {})
        providers[pid] = {
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "builtin": False,
            "scheme": "anthropic" if str(message.get("scheme", "openai")) == "anthropic" else "openai",
            "models": {},
        }
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("provider.added", name=name), "kind": "ok"}
        )

    def _handle_update_provider(self: "_ChatEngine", message: dict) -> None:
        """Обновляет поля пользовательского провайдера."""
        pid = str(message.get("id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(pid)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        if message.get("name") is not None:
            prov["name"] = str(message["name"]).strip() or prov.get("name", pid)
        if message.get("base_url") is not None:
            prov["base_url"] = str(message["base_url"]).strip()
        if message.get("api_key") is not None:
            prov["api_key"] = str(message["api_key"]).strip()
        if message.get("scheme") is not None:
            prov["scheme"] = (
                "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
            )
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": self._t("provider.updated"), "kind": "ok"})

    def _handle_delete_provider(self: "_ChatEngine", message: dict) -> None:
        """Удаляет пользовательского провайдера, встроенные — под защитой."""
        pid = str(message.get("id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(pid)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        if prov.get("builtin"):
            self._post(
                {
                    "type": "toast",
                    "text": self._t("provider.builtin_locked"),
                    "kind": "err",
                }
            )
            return
        del providers[pid]
        if self._config.get("active_provider") == pid:
            self._config["active_provider"] = "deepseek"
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": self._t("provider.deleted"), "kind": "ok"})

    def _handle_add_model(self: "_ChatEngine", message: dict) -> None:
        """Добавляет пользовательскую модель в провайдер."""
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", "")).strip()
        if not model_id:
            self._post(
                {"type": "toast", "text": self._t("model.id_required"), "kind": "err"}
            )
            return
        name = str(message.get("name", "")).strip() or model_id
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        models = prov.setdefault("models", {})
        if model_id in models:
            self._post(
                {
                    "type": "toast",
                    "text": self._t("model.exists", name=model_id),
                    "kind": "err",
                }
            )
            return
        entry: dict[str, Any] = {"name": name, "builtin": False}
        label = str(message.get("label", "")).strip()
        if label:
            entry["name"] = label
        # Per-model настройки: None → не записываем (наследуется глобальное).
        temperature = message.get("temperature")
        if temperature is not None:
            try:
                temperature = float(temperature)
            except (TypeError, ValueError):
                temperature = None
            if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                temperature = None
            if temperature is not None:
                entry["temperature"] = temperature
        max_tokens = message.get("max_tokens")
        if max_tokens is not None:
            try:
                max_tokens = int(max_tokens)
            except (TypeError, ValueError):
                max_tokens = None
            if max_tokens is not None and (max_tokens < 1 or max_tokens > 100000):
                max_tokens = None
            if max_tokens is not None:
                entry["max_tokens"] = max_tokens
        reasoning = message.get("reasoning")
        if reasoning is not None:
            if isinstance(reasoning, str):
                reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
            entry["reasoning"] = bool(reasoning)
        # URL/ключ/схема — только для пользовательских провайдеров.
        if not prov.get("builtin", False):
            if message.get("base_url") is not None:
                entry["base_url"] = str(message["base_url"]).strip()
            if message.get("api_key") is not None:
                entry["api_key"] = str(message["api_key"]).strip()
            if message.get("scheme") is not None:
                entry["scheme"] = (
                    "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
                )
        models[model_id] = entry
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.added", name=model_id), "kind": "ok"}
        )

    def _handle_update_model(self: "_ChatEngine", message: dict) -> None:
        """Обновляет поля пользовательской модели.

        Принимает provider, model_id и опционально name, temperature,
        max_tokens, reasoning, base_url, api_key, scheme. URL/ключ/схему
        можно менять только у не-встроенных моделей.
        """
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post({"type": "toast", "text": self._t("provider.not_found"), "kind": "err"})
            return
        models = prov.get("models", {})
        mdef = models.get(model_id)
        if not isinstance(mdef, dict):
            self._post({"type": "toast", "text": self._t("model.not_found"), "kind": "err"})
            return
        if message.get("name") is not None:
            new_name = str(message["name"]).strip()
            if new_name:
                mdef["name"] = new_name
        temperature = message.get("temperature")
        if "temperature" in message:
            try:
                temperature = float(temperature) if temperature is not None else None
            except (TypeError, ValueError):
                temperature = None
            if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                temperature = None
            mdef["temperature"] = temperature
        max_tokens = message.get("max_tokens")
        if "max_tokens" in message:
            try:
                max_tokens = int(max_tokens) if max_tokens is not None else None
            except (TypeError, ValueError):
                max_tokens = None
            if max_tokens is not None and (max_tokens < 1 or max_tokens > 100000):
                max_tokens = None
            mdef["max_tokens"] = max_tokens
        reasoning = message.get("reasoning")
        if "reasoning" in message:
            if reasoning is None:
                mdef["reasoning"] = None
            else:
                if isinstance(reasoning, str):
                    reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
                mdef["reasoning"] = bool(reasoning)
        if mdef.get("builtin", False):
            if any(
                message.get(key) is not None
                for key in ("base_url", "api_key", "scheme")
            ):
                self._post(
                    {
                        "type": "toast",
                        "text": self._t("model.builtin_locked_fields"),
                        "kind": "err",
                    }
                )
                return
        else:
            if message.get("base_url") is not None:
                mdef["base_url"] = str(message["base_url"]).strip()
            if message.get("api_key") is not None:
                mdef["api_key"] = str(message["api_key"]).strip()
            if message.get("scheme") is not None:
                mdef["scheme"] = (
                    "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
                )
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.updated", name=model_id), "kind": "ok"}
        )

    def _handle_delete_model(self: "_ChatEngine", message: dict) -> None:
        """Удаляет пользовательскую модель, встроенные — под защитой."""
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        models = prov.get("models", {})
        mdef = models.get(model_id)
        if not isinstance(mdef, dict):
            self._post(
                {"type": "toast", "text": self._t("model.not_found"), "kind": "err"}
            )
            return
        if mdef.get("builtin"):
            self._post(
                {
                    "type": "toast",
                    "text": self._t("model.builtin_locked"),
                    "kind": "err",
                }
            )
            return
        del models[model_id]
        if (
            self._config.get("active_provider") == provider
            and self._config.get("active_model") == model_id
        ):
            self._config["active_model"] = next(iter(models), "")
        self._config = self._normalize_config(self._config)
        self._cap.save_config(json.dumps(self._config))
        self._send_state()
        self._post({"type": "toast", "text": self._t("model.deleted"), "kind": "ok"})

    @staticmethod
    def _slugify(text: str) -> str:
        """Преобразует название в идентификатор-слаг."""
        result: list[str] = []
        for ch in text.lower():
            if ch.isalnum() or ch in "-_":
                result.append(ch)
            elif ch.isspace():
                result.append("-")
        slug = "".join(result).strip("-")
        return slug or "provider"

    @staticmethod
    def _random_suffix() -> str:
        """Случайный короткий суффикс для идентификатора провайдера."""
        return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))
