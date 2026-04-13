"""Tests for SSRF protection utilities."""

from unittest.mock import MagicMock, patch

import pytest

from fourdpocket.utils.ssrf import is_safe_url


class TestSSRFBlockedIPs:
    """Verify that internal/private IP ranges are blocked."""

    @pytest.mark.security
    @pytest.mark.parametrize("ip", [
        "127.0.0.1",
        "127.255.255.255",
        "127.1.2.3",
        "10.0.0.1",
        "10.255.255.255",
        "10.1.2.3",
        "172.16.0.1",
        "172.16.255.255",
        "172.31.255.255",
        "172.20.0.1",
        "192.168.0.1",
        "192.168.255.255",
        "169.254.0.1",
        "169.254.255.255",
    ])
    def test_blocked_private_ip_ranges(self, ip):
        """Private and loopback IPs must be rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), (ip, 80))
            ]
            assert is_safe_url(f"http://{ip}/") is False, f"{ip} should be blocked"

    @pytest.mark.security
    @pytest.mark.parametrize("ip", [
        "::1",       # loopback
        "fc00::1",   # ULA
        "fd00::1",   # ULA
    ])
    def test_blocked_ipv6_addresses(self, ip):
        """Loopback and ULA IPv6 addresses must be rejected.

        Note: fe80::/10 (link-local) is NOT blocked by the implementation.
        """
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), (ip, 80))
            ]
            assert is_safe_url(f"http://[{ip}]/") is False, f"{ip} should be blocked"

    @pytest.mark.security
    def test_fe80_link_local_not_blocked(self):
        """fe80::/10 (link-local) is intentionally NOT blocked."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), ("fe80::1", 80))
            ]
            # Link-local is allowed (not in _BLOCKED_NETWORKS)
            assert is_safe_url("http://[fe80::1]/") is True


class TestSSRFAllowedIPs:
    """Verify that public routable IPs are allowed."""

    @pytest.mark.security
    @pytest.mark.parametrize("ip", [
        "8.8.8.8",
        "1.1.1.1",
        "142.250.185.46",  # google.com
        "151.101.1.140",   # reddit.com
    ])
    def test_allowed_public_ips(self, ip):
        """Public IPs must be allowed through."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), (ip, 80))
            ]
            assert is_safe_url(f"http://{ip}/") is True, f"{ip} should be allowed"


class TestSSRFSchemeValidation:
    """Verify that only http/https schemes are permitted."""

    @pytest.mark.security
    @pytest.mark.parametrize("scheme", [
        "ftp",
        "file",
        "gopher",
        "javascript",
        "data",
        "dict",
    ])
    def test_rejects_invalid_schemes(self, scheme):
        """Non-http(s) schemes must be rejected."""
        assert is_safe_url(f"{scheme}://example.com/") is False

    def test_allows_https(self):
        """HTTPS scheme must be allowed for public hosts."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), ("1.1.1.1", 443))
            ]
            assert is_safe_url("https://one.one.one.one/") is True


class TestSSRFHostnameResolution:
    """Verify hostname resolution and edge cases."""

    @pytest.mark.security
    def test_rejects_unspecified_hostname(self):
        """Empty or no hostname must be rejected."""
        assert is_safe_url("http://") is False

    @pytest.mark.security
    def test_rejects_malformed_url(self):
        """Malformed URLs must be rejected safely."""
        assert is_safe_url("not-a-url") is False
        assert is_safe_url("http://") is False

    @pytest.mark.security
    def test_rejects_resolution_failure(self):
        """Unresolvable hostnames must be rejected (fail closed)."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror("Name resolution failed")
            assert is_safe_url("http://this-domain-does-not-exist.example/") is False

    @pytest.mark.security
    def test_resolves_to_multiple_ips_one_blocked(self):
        """If ANY resolved IP is blocked, the URL must be rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            # One IP public, one IP private — should be blocked
            mock_getaddrinfo.return_value = [
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), ("8.8.8.8", 80)),
                (MagicMock(), MagicMock(), MagicMock(), MagicMock(), ("127.0.0.1", 80)),
            ]
            assert is_safe_url("http://multi-lookup.example/") is False


# Import socket at module level for the gaierror reference
import socket
