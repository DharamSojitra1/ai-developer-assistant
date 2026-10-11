import pytest

from app.utils.url_safety import (
    UnsafeURLError,
    is_public_address,
    validate_outbound_url,
)

ALLOWED = ["docs.example.com"]


def resolves_to(*addresses):
    return lambda host, port: list(addresses)


def test_allowlisted_public_https_url_passes():
    assert validate_outbound_url(
        "https://docs.example.com/guide",
        ALLOWED,
        resolver=resolves_to("93.184.215.14"),
    ) == ["93.184.215.14"]


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.example.com/",
        "ftp://docs.example.com/",
        "file:///etc/passwd",
        "https://user:pass@docs.example.com/",
        "https://docs.example.com:8443/",
        "https://evil.example.net/",
        "https://docs.example.com.evil.net/",
        "https:///nohost",
        "not a url",
    ],
)
def test_disallowed_urls_are_rejected(url):
    with pytest.raises(UnsafeURLError):
        validate_outbound_url(url, ALLOWED, resolver=resolves_to("93.184.215.14"))


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata endpoint
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:10.0.0.1",
    ],
)
def test_allowlisted_host_resolving_to_internal_address_is_rejected(address):
    assert not is_public_address(address)

    with pytest.raises(UnsafeURLError, match="non-public"):
        validate_outbound_url(
            "https://docs.example.com/",
            ALLOWED,
            resolver=resolves_to("93.184.215.14", address),
        )


def test_unresolvable_host_is_rejected():
    def fail(host, port):
        raise OSError("no such host")

    with pytest.raises(UnsafeURLError, match="resolve"):
        validate_outbound_url("https://docs.example.com/", ALLOWED, resolver=fail)


def test_host_matching_is_case_and_trailing_dot_insensitive():
    validate_outbound_url(
        "https://DOCS.Example.com./x",
        ALLOWED,
        resolver=resolves_to("93.184.215.14"),
    )
