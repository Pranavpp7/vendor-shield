"""SSRF guard — URL ingestion must never reach internal services."""

import pytest

from services.extraction import UnsafeURLError, _assert_public_http_url


@pytest.mark.parametrize("url", [
    "http://localhost:6333/collections",       # local Qdrant
    "http://127.0.0.1:8000/api/health",        # ourselves
    "http://169.254.169.254/latest/meta-data", # cloud metadata endpoint
    "http://192.168.1.1/admin",                # RFC-1918
    "http://10.0.0.5/",                        # RFC-1918
    "http://[::1]/",                           # IPv6 loopback
    "http://0.0.0.0/",                         # unspecified
])
def test_private_and_reserved_targets_blocked(url):
    with pytest.raises(UnsafeURLError):
        _assert_public_http_url(url)


@pytest.mark.parametrize("url", [
    "ftp://example.com/file.txt",
    "file:///etc/passwd",
    "gopher://example.com/",
    "not-a-url",
])
def test_non_http_schemes_blocked(url):
    with pytest.raises(UnsafeURLError):
        _assert_public_http_url(url)


def test_public_address_allowed():
    # 1.1.1.1 is unambiguously public — no DNS dependency in this test
    _assert_public_http_url("https://1.1.1.1/")
