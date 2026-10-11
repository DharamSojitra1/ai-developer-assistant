"""SSRF guard for any future tool that fetches URLs.

No tool fetches URLs today. A web tool must call `validate_outbound_url`
before every request, including each redirect hop (fetch with redirects
disabled and validate the `Location` itself), and connect to one of the
returned addresses so DNS cannot be re-resolved to an internal host.
"""

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"https"})
ALLOWED_PORTS = frozenset({443})

Resolver = Callable[[str, int], list[str]]


class UnsafeURLError(ValueError):
    pass


def resolve_host(host: str, port: int) -> list[str]:
    return sorted(
        {
            info[4][0]
            for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    )


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])

    # IPv4-mapped IPv6 (::ffff:10.0.0.1) must be judged as the IPv4 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    return ip.is_global and not ip.is_multicast


def validate_outbound_url(
    url: str,
    allowed_hosts: Iterable[str],
    resolver: Resolver = resolve_host,
) -> list[str]:
    """Check `url` against the policy; returns the vetted IP addresses.

    Raises UnsafeURLError if the scheme, port, credentials, host, or any
    resolved address is not allowed.
    """
    try:
        parts = urlsplit(url.strip())
        port = parts.port or 443
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid URL: {exc}") from exc

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only https URLs are allowed")

    if parts.username or parts.password:
        raise UnsafeURLError("URLs with credentials are not allowed")

    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f"Port {port} is not allowed")

    host = (parts.hostname or "").rstrip(".").lower()

    if not host:
        raise UnsafeURLError("URL has no host")

    allowed = {h.rstrip(".").lower() for h in allowed_hosts}

    if host not in allowed:
        raise UnsafeURLError(f"Host '{host}' is not in the allowlist")

    try:
        addresses = resolver(host, port)
    except OSError as exc:
        raise UnsafeURLError(f"Could not resolve '{host}'") from exc

    if not addresses:
        raise UnsafeURLError(f"Could not resolve '{host}'")

    blocked = [a for a in addresses if not is_public_address(a)]

    if blocked:
        raise UnsafeURLError(
            f"Host '{host}' resolves to a non-public address"
        )

    return addresses
