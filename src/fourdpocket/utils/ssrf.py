"""Shared SSRF protection utilities."""

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata / link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def is_safe_url(url: str) -> bool:
    """Return True only if the URL targets a public, routable address.

    Checks:
    - Scheme must be http or https
    - Hostname must resolve
    - Resolved IP must not be in any blocked (internal/loopback) network

    TOCTOU limitation: DNS is resolved at validation time, not at TCP-connect
    time. A DNS rebinding attack can return a public IP here and a private IP
    at connect time. To eliminate this window use ``resolve_and_check`` below,
    which returns the pre-resolved safe IP that callers can pin via an httpx
    transport, ensuring the same address is used for both the check and the
    connection.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for _family, _, _, _, sockaddr in addr_info:
                ip = ipaddress.ip_address(sockaddr[0])
                for network in _BLOCKED_NETWORKS:
                    if ip in network:
                        return False
        except socket.gaierror:
            return False
        return True
    except Exception:
        return False


def resolve_and_check(url: str) -> str | None:
    """Resolve the URL's hostname, verify it is safe, and return the IP string.

    Returns the first safe resolved IP address, or None if the host resolves
    to a blocked address or cannot be resolved. Callers that need DNS-rebinding
    protection should use the returned IP as the connect address (e.g. by
    building an httpx transport that forces connections to this IP while
    passing the original hostname as the SNI/Host header).

    Example usage with httpx (DNS-rebinding-safe):

        ip = resolve_and_check(url)
        if ip is None:
            raise ValueError("URL blocked")
        # Replace hostname with the pre-checked IP in the URL, keeping Host header:
        import httpx
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        safe_url = urlunparse(parsed._replace(netloc=ip))
        async with httpx.AsyncClient() as client:
            r = await client.get(safe_url, headers={"Host": parsed.hostname})
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        hostname = parsed.hostname
        if not hostname:
            return None
        addr_info = socket.getaddrinfo(hostname, None)
        for _family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            blocked = any(ip in net for net in _BLOCKED_NETWORKS)
            if not blocked:
                return ip_str
        return None
    except Exception:
        return None
