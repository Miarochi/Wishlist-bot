from __future__ import annotations

import html
import re

import aiohttp

_OG_TITLE_RE = re.compile(
    rb'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE
)
_OG_TITLE_RE_ALT = re.compile(
    rb'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', re.IGNORECASE
)
_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = aiohttp.ClientTimeout(total=5)
_MAX_BYTES = 200_000
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


async def title_for_item(item: str) -> str | None:
    return await fetch_link_title(item) if _URL_RE.match(item) else None


async def fetch_link_title(url: str) -> str | None:
    try:
        async with aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return None
                body = await response.content.read(_MAX_BYTES)
    except (aiohttp.ClientError, TimeoutError, OSError):
        return None

    for pattern in (_OG_TITLE_RE, _OG_TITLE_RE_ALT, _TITLE_RE):
        match = pattern.search(body)
        if match:
            title = html.unescape(match.group(1).decode("utf-8", errors="ignore")).strip()
            if title:
                return title[:200]
    return None
