"""Управление провайдерами и моделями движка FlowSlice AI.

Миксин ProvidersMixin реализует CRUD-операции над провайдерами и моделями:
выбор активной модели, добавление/обновление/удаление пользовательских
провайдеров и моделей, генерация слагов и случайных суффиксов.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-statements,too-many-branches
# pylint: disable=too-many-locals,too-many-public-methods,too-few-public-methods,line-too-long

import secrets
import threading
from typing import TYPE_CHECKING, Any

from flowslice_ai.config import normalize_max_tokens, normalize_temperature

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
        self._persist_config()
        self._send_state()
        self._post({"type": "toast", "text": self._t("model.selected", name=model), "kind": "ok"})

    def _handle_set_default_model(self: "_ChatEngine", message: dict) -> None:
        """Устанавливает модель по умолчанию для новых чатов."""
        provider = str(message.get("provider", ""))
        model = str(message.get("model", ""))
        providers = self._config.get("providers", {})
        prov = providers.get(provider)
        if not isinstance(prov, dict):
            self._post({"type": "toast", "text": self._t("model.not_found"), "kind": "err"})
            return
        if model not in prov.get("models", {}):
            # Модель могла быть выбрана из подгруженного списка провайдера —
            # в этом случае сначала добавляем её в конфиг.
            info = self._api_model_by_id(provider, model)
            if info is None or not self._ensure_model_from_api(provider, model, info):
                self._post(
                    {"type": "toast", "text": self._t("model.not_found"), "kind": "err"}
                )
                return
        self._config["default_model"] = provider + "::" + model
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.default_set", name=model), "kind": "ok"}
        )

    def _api_model_by_id(
        self: "_ChatEngine", provider: str, model_id: str
    ) -> dict[str, Any] | None:
        """Ищет модель в кэше подгруженного списка провайдера."""
        cached = self._api_models_cache.get(provider)
        if not cached:
            return None
        for item in cached[1]:
            if isinstance(item, dict) and str(item.get("id", "")) == model_id:
                return item
        return None

    def _ensure_model_from_api(
        self: "_ChatEngine", provider: str, model_id: str, info: dict[str, Any] | None = None
    ) -> bool:
        """Добавляет модель из подгруженного списка в конфиг, если её там нет.

        Переносит подтверждённые провайдером признаки (зрение, цену), чтобы
        выбранная модель вела себя так же, как при ручном добавлении.
        """
        info = info or {}
        prov = self._config.get("providers", {}).get(provider)
        if not isinstance(prov, dict):
            return False
        models = prov.setdefault("models", {})
        if model_id in models:
            return True
        entry: dict[str, Any] = {
            "name": str(info.get("name") or model_id),
            "builtin": False,
        }
        vision = info.get("vision")
        if isinstance(vision, bool):
            entry["vision"] = vision
            entry["vision_source"] = "provider"
        for key in ("price_in", "price_out"):
            value = info.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                entry[key] = float(value)
        if "price_in" in entry or "price_out" in entry:
            entry["price_source"] = "provider"
        models[model_id] = entry
        return True

    def _handle_set_api_model(self: "_ChatEngine", message: dict) -> None:
        """Делает активной модель, выбранную из подгруженного списка провайдера."""
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", "")).strip()
        if not model_id:
            self._post({"type": "toast", "text": self._t("model.id_required"), "kind": "err"})
            return
        if provider not in self._config.get("providers", {}):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        info = self._api_model_by_id(provider, model_id)
        if info is None:
            info = {
                "name": message.get("name"),
                "vision": message.get("vision"),
                "price_in": message.get("price_in"),
                "price_out": message.get("price_out"),
            }
        self._ensure_model_from_api(provider, model_id, info)
        self._config["active_provider"] = provider
        self._config["active_model"] = model_id
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.selected", name=model_id), "kind": "ok"}
        )

    def _handle_import_api_model(self: "_ChatEngine", message: dict) -> None:
        """Добавляет модель из подгруженного списка в конфиг, не делая активной.

        Используется во вкладке настроек «Модели», чтобы можно было открыть
        настройки модели, не переключая модель текущего чата.
        """
        provider = str(message.get("provider", ""))
        model_id = str(message.get("model_id", "")).strip()
        if not model_id:
            self._post({"type": "toast", "text": self._t("model.id_required"), "kind": "err"})
            return
        if provider not in self._config.get("providers", {}):
            self._post(
                {"type": "toast", "text": self._t("provider.not_found"), "kind": "err"}
            )
            return
        info = self._api_model_by_id(provider, model_id) or {
            "name": message.get("name"),
            "vision": message.get("vision"),
            "price_in": message.get("price_in"),
            "price_out": message.get("price_out"),
        }
        self._ensure_model_from_api(provider, model_id, info)
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.added", name=model_id), "kind": "ok"}
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
        scheme = "anthropic" if str(message.get("scheme", "openai")) == "anthropic" else "openai"
        providers[pid] = {
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "builtin": False,
            "scheme": scheme,
            "models": {},
        }
        # Первая модель может создаваться вместе с провайдером (форма из вкладки «Персональные»).
        model_id = str(message.get("model_id", "")).strip()
        if model_id:
            label = str(message.get("label", "")).strip() or model_id
            providers[pid]["models"][model_id] = {
                "name": label,
                "builtin": False,
                "base_url": base_url,
                "api_key": api_key,
                "scheme": scheme,
            }
            # Сразу делаем нового провайдера и модель активными.
            self._config["active_provider"] = pid
            self._config["active_model"] = model_id
        self._config = self._normalize_config(self._config)
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("provider.added", name=name), "kind": "ok"}
        )
        if model_id:
            self._start_vision_lookup(pid, model_id)

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
            api_key = str(message["api_key"]).strip()
            # Пустое поле = «не менять ключ» (UI не предзаполняет секрет).
            if api_key:
                prov["api_key"] = api_key
        if message.get("scheme") is not None:
            prov["scheme"] = (
                "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
            )
        self._config = self._normalize_config(self._config)
        self._persist_config()
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
        self._persist_config()
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
        # Цена за 1М токенов (необязательно): у персональных моделей её взять неоткуда.
        for price_key in ("price_in", "price_out"):
            price_value = self._normalize_price(message.get(price_key))
            if price_value is not None:
                entry[price_key] = price_value
        if "price_in" in entry or "price_out" in entry:
            entry["price_source"] = "manual"
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
        self._persist_config()
        self._send_state()
        self._post(
            {"type": "toast", "text": self._t("model.added", name=model_id), "kind": "ok"}
        )
        # Пытаемся уточнить поддержку изображений у провайдера (OpenRouter).
        self._start_vision_lookup(provider, model_id)

    def _start_vision_lookup(self: "_ChatEngine", provider: str, model_id: str) -> None:
        """Запускает фоновое определение поддержки изображений у модели."""
        thread = threading.Thread(
            target=self._vision_lookup_worker,
            args=(provider, model_id),
            daemon=True,
        )
        thread.start()

    def _vision_lookup_worker(self: "_ChatEngine", provider: str, model_id: str) -> None:
        """Уточняет зрение модели через API провайдера и сохраняет результат."""
        value = self._resolve_vision_for(provider, model_id)
        if value is None:
            return
        prov = self._config.get("providers", {}).get(provider)
        if not isinstance(prov, dict):
            return
        mdef = prov.get("models", {}).get(model_id)
        if not isinstance(mdef, dict):
            return
        mdef["vision"] = bool(value)
        # Значение подтверждено самим провайдером.
        mdef["vision_source"] = "provider"
        self._persist_config()
        self._send_state()

    @staticmethod
    def _normalize_price(value: Any) -> float | None:
        """Нормализует цену за 1М токенов.

        Возвращает None, если значение пустое, не число или вне разумных границ.
        """
        if value is None:
            return None
        try:
            price = float(value)
        except (TypeError, ValueError):
            return None
        if price < 0 or price > 100000:
            return None
        return round(price, 4)

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
            mdef["temperature"] = normalize_temperature(temperature)
        max_tokens = message.get("max_tokens")
        if "max_tokens" in message:
            mdef["max_tokens"] = normalize_max_tokens(max_tokens)
        reasoning = message.get("reasoning")
        if "reasoning" in message:
            if reasoning is None:
                mdef["reasoning"] = None
            else:
                if isinstance(reasoning, str):
                    reasoning = reasoning.strip().lower() in ("1", "true", "yes", "on")
                mdef["reasoning"] = bool(reasoning)
        if "vision" in message:
            vision = message.get("vision")
            if vision is None:
                mdef["vision"] = None
            elif isinstance(vision, str):
                mdef["vision"] = vision.strip().lower() in ("1", "true", "yes", "on")
            else:
                mdef["vision"] = bool(vision)
            # Значение выставлено пользователем вручную.
            mdef["vision_source"] = "manual"
        if "price_in" in message or "price_out" in message:
            # Цена может быть задана вручную: у части провайдеров её нет в API,
            # а у персональных моделей — неоткуда взять.
            for price_key in ("price_in", "price_out"):
                if price_key in message:
                    price_value = self._normalize_price(message.get(price_key))
                    if price_value is None:
                        mdef.pop(price_key, None)
                    else:
                        mdef[price_key] = price_value
            if mdef.get("price_in") is None and mdef.get("price_out") is None:
                mdef.pop("price_source", None)
            else:
                mdef["price_source"] = "manual"
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
                api_key = str(message["api_key"]).strip()
                # Пустое поле = «не менять ключ» (UI не предзаполняет секрет).
                if api_key:
                    mdef["api_key"] = api_key
            if message.get("scheme") is not None:
                mdef["scheme"] = (
                    "anthropic" if str(message["scheme"]) == "anthropic" else "openai"
                )
        self._config = self._normalize_config(self._config)
        self._persist_config()
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
        self._persist_config()
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
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(4))
