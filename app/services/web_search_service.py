"""Live web search through the Tavily API.

Tavily returns cleaned page text with every result, so the app never
fetches arbitrary URLs itself. Identical queries are answered from a short
in-memory cache to save paid API calls.
"""

import time
from collections import OrderedDict
from collections.abc import Callable

import httpx

from app.config import (
    MOCK_MODE,
    REQUEST_TIMEOUT,
    TAVILY_API_KEY,
    WEB_SEARCH_CACHE_TTL_SECONDS,
    WEB_SEARCH_MAX_RESULTS,
)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
# Small on purpose: every result is re-sent on each later LLM call, and the
# Groq free tier allows 8,000 tokens per minute.
MAX_CONTENT_CHARS = 600
MAX_ANSWER_CHARS = 600
MAX_TITLE_CHARS = 200
MAX_CACHE_ENTRIES = 256
LINKABLE_SCHEMES = ("https://", "http://")


class WebSearchNotConfiguredError(Exception):
    pass


class WebSearchError(Exception):
    pass


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def cache_key(query: str, recent: bool) -> str:
    return f"{'recent' if recent else 'any'}:{normalize_query(query)}"


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _mock_response(query: str) -> dict:
    return {
        "answer": None,
        "results": [
            {
                "title": f"Mock result for: {query}",
                "url": "https://example.com/mock-search-result",
                "content": "Mock web search content. Set MOCK_MODE=false and "
                "TAVILY_API_KEY to search the live web.",
                "published_date": None,
            }
        ],
    }


class WebSearchService:
    def __init__(
        self,
        api_key: str | None = TAVILY_API_KEY,
        max_results: int = WEB_SEARCH_MAX_RESULTS,
        cache_ttl_seconds: int = WEB_SEARCH_CACHE_TTL_SECONDS,
        mock_mode: bool = MOCK_MODE,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.api_key = api_key
        self.max_results = max_results
        self.cache_ttl_seconds = cache_ttl_seconds
        self.mock_mode = mock_mode
        self.transport = transport
        self.clock = clock
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    async def search(self, query: str, recent: bool = False) -> dict:
        """{"answer": str | None, "results": [{title, url, content,
        published_date}, ...]}.

        `recent` restricts the search to news from the last month.
        Raises WebSearchNotConfiguredError without an API key (outside mock
        mode) and WebSearchError when the API call fails.
        """
        if self.mock_mode:
            return _mock_response(query)

        if not self.api_key:
            raise WebSearchNotConfiguredError("TAVILY_API_KEY is not set")

        key = cache_key(query, recent)
        cached = self._cached(key)

        if cached is not None:
            return cached

        response = await self._fetch(query, recent)
        self._store(key, response)

        return response

    def _cached(self, key: str) -> dict | None:
        entry = self._cache.get(key)

        if entry is None:
            return None

        expires_at, results = entry

        if self.clock() >= expires_at:
            del self._cache[key]
            return None

        return results

    def _store(self, key: str, response: dict) -> None:
        if self.cache_ttl_seconds <= 0:
            return

        self._cache[key] = (self.clock() + self.cache_ttl_seconds, response)
        self._cache.move_to_end(key)

        while len(self._cache) > MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    async def _fetch(self, query: str, recent: bool) -> dict:
        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": self.max_results,
            # A one-paragraph summary often answers the question on its own,
            # so the model needs fewer and shorter results.
            "include_answer": True,
        }

        if recent:
            payload.update(topic="news", time_range="month")

        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    TAVILY_SEARCH_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Tavily request failed: {exc!r}") from exc

        if response.status_code != 200:
            raise WebSearchError(
                f"Tavily returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise WebSearchError("Tavily returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise WebSearchError("Tavily returned an unexpected payload")

        raw_results = data.get("results") or []
        answer = data.get("answer")

        return {
            "answer": (
                _truncate(answer, MAX_ANSWER_CHARS)
                if isinstance(answer, str) and answer.strip()
                else None
            ),
            "results": self._parse_results(raw_results),
        }

    def _parse_results(self, raw_results: list) -> list[dict]:
        return [
            {
                "title": _truncate(str(item.get("title") or ""), MAX_TITLE_CHARS),
                "url": item["url"],
                "content": _truncate(
                    str(item.get("content") or ""), MAX_CONTENT_CHARS
                ),
                "published_date": item.get("published_date"),
            }
            for item in raw_results[: self.max_results]
            if isinstance(item, dict)
            and isinstance(item.get("url"), str)
            and item["url"].lower().startswith(LINKABLE_SCHEMES)
        ]
