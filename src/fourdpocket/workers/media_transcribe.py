"""Video transcription (ASR) + on-screen-text OCR for video items.

Composes existing primitives so reels/shorts/tiktok (and YouTube videos without
a published transcript) contribute their *spoken* and *on-screen* text to search:

  * download the media — a direct CDN mp4 (preferred; e.g. instaloader's
    ``video_url``) or yt-dlp on the page URL as a fallback;
  * speech-to-text via Groq Whisper (the same provider as ``/transcribe``);
  * optional on-screen text via ffmpeg frame sampling + tesseract OCR.

Groq Whisper accepts mp4 directly (≤25 MB), so the common reel/short case needs
no ffmpeg; ffmpeg is only used to downsize oversized audio and to sample frames
for OCR. This module is intentionally best-effort: callers (the ``transcribed``
enrichment stage) treat all failures as non-fatal so a missing transcript never
blocks the rest of enrichment.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import httpx

from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _prefer_ipv4():
    """Force IPv4-only DNS resolution within the block.

    Some hosts (e.g. the DeluxHost VPS) advertise an IPv6 default route that
    isn't actually routable, so dual-stack targets like Instagram's CDN fail
    with ``[Errno 101] Network is unreachable`` on the v6 attempt. yt-dlp gets
    ``-4``; for httpx we constrain ``getaddrinfo`` to A records here.
    """
    orig = socket.getaddrinfo

    def _v4(host, port, family=0, *args, **kwargs):
        return orig(host, port, socket.AF_INET, *args, **kwargs)

    socket.getaddrinfo = _v4
    try:
        yield
    finally:
        socket.getaddrinfo = orig

_WHISPER_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
_MAX_BYTES = 25 * 1024 * 1024  # Groq Whisper hard limit
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_SEGMENT_TARGET_CHARS = 600  # group ASR segments into ~screenful transcript chunks
_TRANSCRIPT_SECTION_BASE_ORDER = 10_000  # keep ASR/OCR sections after processor sections


class TranscriptionUnavailableError(Exception):
    """No transcription provider is configured. Non-fatal: the stage records it
    and lets downstream enrichment proceed on whatever text already exists."""


def _video_source(item) -> tuple[str, str] | None:
    """Pick the best transcribable media source for an item.

    Returns ``("direct", cdn_url)`` when the processor captured a downloadable
    video file URL (preferred), else ``("ytdlp", page_url)`` for known video
    platforms, else ``None`` when the item has no video to transcribe.
    """
    for m in item.media or []:
        if m.get("type") != "video":
            continue
        url = m.get("url") or ""
        # The YouTube processor stores a role="external" page reference, not a
        # media file — skip it; yt-dlp handles youtube via the page URL below.
        if (
            url.startswith("http")
            and m.get("role") != "external"
            and "youtube.com" not in url
            and "youtu.be" not in url
        ):
            return ("direct", url)

    url = item.url or ""
    platform = item.source_platform.value if item.source_platform else ""
    if (
        platform in ("youtube", "instagram", "tiktok")
        or "/reel/" in url
        or "/reels/" in url
        or "/shorts/" in url
        or "tiktok.com" in url
    ):
        return ("ytdlp", url)
    return None


# Hosts that block datacenter IPs and must egress via the residential proxy.
_PROXIED_HOSTS = ("cdninstagram.com", "instagram.com", "fbcdn.net",
                  "tiktok.com", "tiktokcdn.com")


def _media_proxy_for(url: str, settings) -> str | None:
    """Return the configured media proxy iff this URL targets a host that needs
    residential egress (Instagram/TikTok); else None (download directly)."""
    proxy = (settings.enrichment.media_proxy or "").strip()
    if not proxy:
        return None
    low = (url or "").lower()
    return proxy if any(h in low for h in _PROXIED_HOSTS) else None


def _download_direct(url: str, dest_dir: str, proxy: str | None = None) -> str | None:
    """Stream a direct media URL to disk (SSRF-guarded, size-capped).

    When ``proxy`` is set, egress + DNS happen proxy-side (socks5h), so the
    local IPv4-forcing is skipped; otherwise we force IPv4 (this host's v6 is
    not routable).
    """
    from fourdpocket.workers.media_downloader import _is_safe_media_url

    if not _is_safe_media_url(url):
        logger.warning("SSRF blocked transcription media URL: %s", url)
        return None
    path = Path(dest_dir) / "media.mp4"
    # Allow the video to exceed the Whisper limit a bit — we downsize to audio
    # via ffmpeg afterward when needed.
    hard_cap = _MAX_BYTES * 8
    client_kwargs: dict = {"timeout": 60, "follow_redirects": True}
    if proxy:
        client_kwargs["proxy"] = proxy
    dns_ctx = contextlib.nullcontext() if proxy else _prefer_ipv4()
    try:
        with dns_ctx, httpx.Client(**client_kwargs) as client, client.stream(
            "GET", url, headers={"User-Agent": _BROWSER_UA},
        ) as r:
            r.raise_for_status()
            total = 0
            with open(path, "wb") as f:
                for chunk in r.iter_bytes(65536):
                    total += len(chunk)
                    if total > hard_cap:
                        logger.warning("transcription media exceeded cap, truncating: %s", url)
                        break
                    f.write(chunk)
        return str(path) if path.exists() and path.stat().st_size > 0 else None
    except Exception as e:
        logger.warning("direct media download failed (%s): %s", url, e)
        return None


def _download_ytdlp(url: str, dest_dir: str, proxy: str | None = None) -> str | None:
    """Download bestaudio via yt-dlp (extract to mp3 when ffmpeg is available)."""
    from fourdpocket.workers.media_downloader import _is_safe_media_url

    if not _is_safe_media_url(url):
        logger.warning("SSRF blocked yt-dlp transcription URL: %s", url)
        return None
    out_tmpl = str(Path(dest_dir) / "audio.%(ext)s")
    # --socket-timeout keeps an auth-walled/unreachable source from hanging the
    # worker. With a proxy, egress/DNS go proxy-side; without one, force IPv4
    # (this host's v6 isn't routable).
    base = ["yt-dlp", "--no-playlist", "--socket-timeout", "30",
            "-f", "bestaudio/best", "--max-filesize", "100M", "-o", out_tmpl, url]
    if proxy:
        base += ["--proxy", proxy]
    else:
        base.insert(1, "-4")
    # Prefer audio extraction (needs ffmpeg); fall back to the raw bestaudio
    # container if extraction isn't possible.
    attempts = [base + ["-x", "--audio-format", "mp3"], base]
    for cmd in attempts:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as e:
            logger.warning("yt-dlp transcription download failed: %s", e)
            continue
        files = sorted(Path(dest_dir).glob("audio.*"))
        if files:
            return str(files[0])
    return None


def _ensure_under_limit(path: str, dest_dir: str) -> str | None:
    """Return a path whose size is ≤ the Whisper limit, transcoding audio with
    ffmpeg when the source is too large. Returns None if it can't be shrunk."""
    p = Path(path)
    if p.stat().st_size <= _MAX_BYTES:
        return str(p)
    if not shutil.which("ffmpeg"):
        return None
    out = str(Path(dest_dir) / "audio_small.mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000",
             "-b:a", "64k", out],
            capture_output=True, timeout=300,
        )
        if Path(out).exists() and Path(out).stat().st_size <= _MAX_BYTES:
            return out
    except Exception as e:
        logger.warning("ffmpeg audio downsize failed: %s", e)
    return None


def _whisper_segments(path: str, groq_key: str, model: str,
                      proxy: str | None = None) -> list[dict]:
    """Transcribe via Groq Whisper. Returns [{text,start,end}] segments.

    Routes through ``proxy`` when set so the ASR call works on hosts whose own
    egress can't reach the API (the same media_proxy used for downloads)."""
    with open(path, "rb") as f:
        data = f.read()
    with httpx.Client(timeout=180, proxy=proxy) as client:
        resp = client.post(
            _WHISPER_ENDPOINT,
            headers={"Authorization": f"Bearer {groq_key}"},
            files={"file": (Path(path).name, data, "application/octet-stream")},
            data={"model": model, "response_format": "verbose_json"},
        )
    resp.raise_for_status()
    payload = resp.json()
    out: list[dict] = []
    for s in payload.get("segments") or []:
        text = (s.get("text") or "").strip()
        if text:
            out.append({
                "text": text,
                "start": float(s.get("start", 0.0)),
                "end": float(s.get("end", 0.0)),
            })
    if not out:
        text = (payload.get("text") or "").strip()
        if text:
            out.append({"text": text, "start": 0.0, "end": 0.0})
    return out


def _ocr_frames(video_path: str, dest_dir: str, max_frames: int = 12) -> str:
    """Sample frames (1 per 2s, capped) and OCR them. Best-effort; "" on any gap."""
    if not (shutil.which("ffmpeg") and shutil.which("tesseract")):
        return ""
    frames_dir = Path(dest_dir) / "frames"
    frames_dir.mkdir(exist_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vf", "fps=1/2",
             "-frames:v", str(max_frames), str(frames_dir / "f%03d.png")],
            capture_output=True, timeout=120,
        )
    except Exception as e:
        logger.debug("ffmpeg frame sampling failed: %s", e)
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for img in sorted(frames_dir.glob("*.png")):
        try:
            r = subprocess.run(["tesseract", str(img), "stdout"],
                               capture_output=True, text=True, timeout=30)
        except Exception:
            continue
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            key = line.lower()
            if len(line) >= 4 and key not in seen:
                seen.add(key)
                lines.append(line)
    return "\n".join(lines).strip()


def _group_segments(segments: list[dict], seed: str) -> list[Section]:
    """Group ASR segments into ~screenful transcript_segment sections."""
    sections: list[Section] = []
    order = _TRANSCRIPT_SECTION_BASE_ORDER
    buf: list[str] = []
    buf_start: float | None = None
    buf_end = 0.0

    def flush() -> None:
        nonlocal order, buf, buf_start, buf_end
        if not buf:
            return
        sections.append(Section(
            id=make_section_id(seed, order),
            kind="transcript_segment",
            order=order,
            role="main",
            text=" ".join(buf).strip(),
            timestamp_start_s=buf_start,
            timestamp_end_s=buf_end,
            extra={"source": "asr"},
        ))
        order += 1
        buf = []
        buf_start = None

    for s in segments:
        if buf_start is None:
            buf_start = s["start"]
        buf.append(s["text"])
        buf_end = s["end"]
        if sum(len(x) for x in buf) > _SEGMENT_TARGET_CHARS:
            flush()
    flush()
    return sections


def transcribe_item(item, settings) -> list[Section]:
    """Download + transcribe (+OCR) an item's video. Returns new Sections.

    Returns ``[]`` when the item has no transcribable video or nothing usable
    was produced. Raises :class:`TranscriptionUnavailableError` when no provider key
    is configured (caller treats it as a recorded, non-fatal skip).
    """
    from fourdpocket.ai.factory import get_resolved_ai_config

    src = _video_source(item)
    if not src:
        return []

    groq_key = (get_resolved_ai_config() or {}).get("groq_api_key", "")
    if not groq_key:
        raise TranscriptionUnavailableError(
            "no transcription provider configured (set FDP_AI__GROQ_API_KEY)"
        )

    mode, url = src
    seed = item.url or str(item.id)
    with tempfile.TemporaryDirectory(prefix="fdp_tx_") as tmp:
        media_path = (
            _download_direct(url, tmp, proxy=_media_proxy_for(url, settings))
            if mode == "direct"
            else _download_ytdlp(url, tmp, proxy=_media_proxy_for(url, settings))
        )
        # Direct CDN URLs (e.g. Instagram) expire — fall back to yt-dlp on the page.
        if not media_path and mode == "direct" and item.url:
            media_path = _download_ytdlp(
                item.url, tmp, proxy=_media_proxy_for(item.url, settings)
            )
        if not media_path:
            raise RuntimeError("could not download media for transcription")

        # OCR runs on the video file (before any audio-only downsize).
        ocr_text = ""
        if settings.enrichment.ocr_video_frames:
            ocr_text = _ocr_frames(media_path, tmp)

        sections: list[Section] = []
        asr_path = _ensure_under_limit(media_path, tmp)
        if asr_path:
            segments = _whisper_segments(
                asr_path, groq_key, settings.enrichment.transcribe_model,
                proxy=(settings.enrichment.media_proxy or None),
            )
            sections.extend(_group_segments(segments, seed))
        else:
            logger.warning("media too large for transcription and could not be shrunk: %s", seed)

        if ocr_text:
            sections.append(Section(
                id=make_section_id(seed, _TRANSCRIPT_SECTION_BASE_ORDER + 9_000),
                kind="ocr_text",
                order=_TRANSCRIPT_SECTION_BASE_ORDER + 9_000,
                role="supplemental",
                text=ocr_text,
                extra={"source": "frame_ocr"},
            ))
        return sections
