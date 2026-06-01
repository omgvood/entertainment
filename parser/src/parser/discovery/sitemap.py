"""Sitemap-дискавери: парсим sitemap.xml, фильтруем <loc> по regex."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

from .base import DiscoveredUrl, DiscoveryStrategy


_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class SitemapDiscovery(DiscoveryStrategy):
    def __init__(
        self,
        client: httpx.AsyncClient,
        source_name: str,
        url: str,
        url_pattern: str | None = None,
    ) -> None:
        super().__init__(client, source_name)
        self.url = url
        self.url_pattern = re.compile(url_pattern) if url_pattern else None

    async def discover(self) -> list[DiscoveredUrl]:
        resp = await self.client.get(self.url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        urls: list[str] = []
        # обычный sitemap
        for loc in root.findall(f"{_SITEMAP_NS}url/{_SITEMAP_NS}loc"):
            if loc.text:
                urls.append(loc.text.strip())
        # sitemap index → отдельные sitemap'ы пока не разворачиваем рекурсивно
        # (можно добавить когда понадобится)

        if self.url_pattern is not None:
            urls = [u for u in urls if self.url_pattern.search(u)]

        return [DiscoveredUrl(url=u, source=self.source_name) for u in urls]
