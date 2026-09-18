"""Проверка сетевых адресов провайдеров FlowSlice AI.

Плагин обращается только к явно заданным пользователем API-эндпоинтам.
Модуль защищает от подстановки опасных схем (``file://``, ``ftp://``) и
адресов локальной сети, чтобы введённый base_url не превратился в SSRF
или чтение локальных файлов.
"""

import ipaddress
import urllib.parse

from flowslice_ai.errors import ConfigError

_ALLOWED_SCHEMES = ("http", "https")
# Имена хостов, которые заведомо указывают на локальную машину.
_LOCAL_HOSTS = ("localhost", "localhost.localdomain", "ip6-localhost")


def _is_blocked_address(host: str) -> bool:
    """Возвращает True, если host — петлевой, приватный или служебный адрес."""
    lowered = host.strip("[]").lower()
    if lowered in _LOCAL_HOSTS or lowered.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        # Не IP-литерал: имя хоста проверить без DNS-запроса нельзя.
        return False
    return bool(
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def normalize_base_url(raw: str, allow_empty: bool = False) -> str:
    """Проверяет и нормализует базовый URL провайдера.

    Разрешены только http/https, без учётных данных в URL и без адресов
    локальной сети. Возвращает URL без завершающего слэша.

    Raises:
        ConfigError: с кодом-ключом i18n, если URL недопустим.
    """
    value = str(raw or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ConfigError("provider.bad_url")
    if any(char.isspace() for char in value):
        raise ConfigError("provider.bad_url")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ConfigError("provider.bad_url_scheme")
    if parsed.username or parsed.password:
        raise ConfigError("provider.bad_url_credentials")
    host = parsed.hostname or ""
    if not host:
        raise ConfigError("provider.bad_url_host")
    if _is_blocked_address(host):
        raise ConfigError("provider.bad_url_host")
    return value.rstrip("/")
