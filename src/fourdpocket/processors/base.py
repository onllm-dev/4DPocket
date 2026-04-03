"""Base processor interface and result dataclass."""

import enum
import ipaddress
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from lxml import html as lxml_html

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch (not targeting internal networks)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip = ipaddress.ip_address(sockaddr[0])
                for network in _BLOCKED_NETWORKS:
                    if ip in network:
                        return False
        except socket.gaierror:
            return False
        return True
    except Exception:
        return False


class ProcessorStatus(str, enum.Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


@dataclass(frozen=True)
class ProcessorResult:
    """Immutable result from a content processor."""

    title: str | None = None
    description: str | None = None
    content: str | None = None
    raw_content: str | None = None
    media: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source_platform: str = "generic"
    item_type: str = "url"
    status: ProcessorStatus = ProcessorStatus.success
    error: str | None = None


class BaseProcessor(ABC):
    """Abstract base class for content processors.

    Subclasses declare url_patterns (regexes) they handle and implement process().
    Shared utilities for HTTP fetching and OG metadata extraction are provided.
    """

    url_patterns: list[str] = []
    priority: int = 0  # higher = matched first

    @abstractmethod
    async def process(self, url: str, **kwargs) -> ProcessorResult:
        """Extract content from the given URL."""
        ...

    async def can_handle(self, url: str) -> bool:
        """Optional extra check beyond URL pattern matching."""
        return True

    async def _fetch_url(
        self, url: str, timeout: float = 30.0, follow_redirects: bool = True
    ) -> httpx.Response:
        """Fetch a URL with proper headers and timeout.

        Redirects are followed manually so each target is SSRF-checked.
        """
        if not _is_safe_url(url):
            raise ValueError("URL blocked: targets internal network")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; 4DPocket/0.1; "
                "+https://github.com/4dpocket)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        max_redirects = 5 if follow_redirects else 0
        current_url = url
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for _ in range(max_redirects + 1):
                response = await client.get(current_url, headers=headers)
                if response.is_redirect and max_redirects > 0:
                    location = response.headers.get("location", "")
                    if not location:
                        break
                    # Resolve relative redirects
                    if location.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(current_url)
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"
                    # SSRF check on redirect target
                    if not _is_safe_url(location):
                        raise ValueError("Redirect blocked: targets internal network")
                    current_url = location
                else:
                    response.raise_for_status()
                    return response
        response.raise_for_status()
        return response

    def _extract_og_metadata(self, html_content: str) -> dict:
        """Extract Open Graph and meta tag metadata from HTML."""
        metadata = {}
        try:
            doc = lxml_html.fromstring(html_content)
        except Exception:
            return metadata

        # Open Graph tags
        for meta in doc.xpath("//meta[starts-with(@property, 'og:')]"):
            prop = meta.get("property", "")[3:]  # strip 'og:'
            content = meta.get("content", "")
            if prop and content:
                metadata[f"og_{prop}"] = content

        # Standard meta tags
        for name_attr in ("name", "property"):
            for meta in doc.xpath(f"//meta[@{name_attr}]"):
                name = meta.get(name_attr, "")
                content = meta.get("content", "")
                if name in ("description", "author", "keywords") and content:
                    metadata[name] = content

        # Title tag
        title_el = doc.xpath("//title/text()")
        if title_el:
            metadata["html_title"] = title_el[0].strip()

        # Favicon
        for link in doc.xpath("//link[@rel='icon' or @rel='shortcut icon']"):
            href = link.get("href", "")
            if href:
                metadata["favicon"] = href
                break

        # JSON-LD
        for script in doc.xpath("//script[@type='application/ld+json']"):
            if script.text:
                metadata["json_ld_raw"] = script.text.strip()
                break

        return metadata
