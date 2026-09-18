"""Тесты валидации base_url (защита от SSRF и некорректных адресов)."""
from __future__ import annotations

import pytest

from flowslice_ai.engine.net import normalize_base_url
from flowslice_ai.errors import ConfigError


def test_normalize_base_url_strips_trailing_slash() -> None:
    """Корректный https-адрес возвращается без завершающего слэша."""
    assert normalize_base_url("https://api.example.com/v1/") == "https://api.example.com/v1"


def test_normalize_base_url_allows_empty_when_requested() -> None:
    """Пустой адрес допустим только при allow_empty=True."""
    assert normalize_base_url("", allow_empty=True) == ""
    with pytest.raises(ConfigError) as err:
        normalize_base_url("")
    assert str(err.value) == "provider.bad_url"


@pytest.mark.parametrize(
    "url, expected",
    [
        ("ftp://api.example.com", "provider.bad_url_scheme"),
        ("file:///etc/passwd", "provider.bad_url_scheme"),
        ("api.example.com", "provider.bad_url_scheme"),
    ],
)
def test_normalize_base_url_rejects_schemes(url: str, expected: str) -> None:
    """Разрешены только http и https с явной схемой."""
    with pytest.raises(ConfigError) as err:
        normalize_base_url(url)
    assert str(err.value) == expected


def test_normalize_base_url_rejects_credentials() -> None:
    """Логин и пароль в адресе запрещены."""
    with pytest.raises(ConfigError) as err:
        normalize_base_url("https://user:pass@api.example.com")
    assert str(err.value) == "provider.bad_url_credentials"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",
        "http://127.0.0.1:8080",
        "http://192.168.1.10:8000",
        "http://10.0.0.5",
        "http://169.254.1.1",
    ],
)
def test_normalize_base_url_blocks_local_hosts(url: str) -> None:
    """Локальные и приватные адреса недопустимы (защита от SSRF)."""
    with pytest.raises(ConfigError) as err:
        normalize_base_url(url)
    assert str(err.value) == "provider.bad_url_host"


def test_normalize_base_url_allows_public_ip_and_domain() -> None:
    """Публичный IP и доменное имя пропускаются."""
    assert normalize_base_url("https://93.184.216.34/v1") == "https://93.184.216.34/v1"
    assert normalize_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
