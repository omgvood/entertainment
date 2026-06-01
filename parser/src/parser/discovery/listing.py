"""Listing-дискавери: скачиваем страницу, выдёргиваем все <a href>, фильтруем по regex."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from .base import DiscoveredUrl, DiscoveryStrategy


class ListingDiscovery(DiscoveryStrategy):
    """Кидает GET на url, собирает все ссылки, проходящие по url_pattern."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        source_name: str,
        url: str,
        url_pattern: str,
    ) -> None:
        super().__init__(client, source_name)
        self.url = url
        self.url_pattern = re.compile(url_pattern)

    async def discover(self) -> list[DiscoveredUrl]:
        resp = await self.client.get(self.url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()

        tree = HTMLParser(resp.text)
        seen: set[str] = set()
        result: list[DiscoveredUrl] = []
        for a in tree.css("a[href]"):
            href = a.attributes.get("href")
            if not href:
                continue
            if not self.url_pattern.search(href):
                continue
            absolute = urljoin(self.url, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            result.append(DiscoveredUrl(url=absolute, source=self.source_name))
        return result
