"""Network utilities to ensure reliable socket resolution and avoid broken IPv6 routes."""

from __future__ import annotations

import socket

_ORIG_GETADDRINFO = socket.getaddrinfo


def _force_ipv4_getaddrinfo(
    host: str | None,
    port: str | int | None,
    family: int = 0,
    socktype: int = 0,
    proto: int = 0,
    flags: int = 0,
):
    """Intercept socket.getaddrinfo to force IPv4 when family is unspecified (0 / AF_UNSPEC).

    This prevents timeouts and 'stream reading error / wsarecv' on ISP networks (such as
    Reliance Jio or Airtel in India) where Google Cloud's IPv6 range (2001:4860::) experiences
    blackholing or packet drop.
    """
    if family in (0, socket.AF_UNSPEC):
        family = socket.AF_INET
    return _ORIG_GETADDRINFO(host, port, family, socktype, proto, flags)


def enable_ipv4_preference() -> None:
    """Enforce IPv4 address resolution globally and inject native Windows trust store."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass
    socket.getaddrinfo = _force_ipv4_getaddrinfo
