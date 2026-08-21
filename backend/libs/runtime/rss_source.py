from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx

from core.settings import settings
from libs.models.workflow import WorkflowNode


@dataclass(frozen=True)
class RssFeedItem:
    source: str
    title: str
    link: str
    pub_date: str
    description: str
    uncertain: bool = False
    publisher: str | None = None
    author: str | None = None
    image_url: str | None = None
    content: str | None = None
    match_type: str = "direct"
    query_topic: str | None = None


class RssSource(Protocol):
    async def fetch(self, node: WorkflowNode, query: str = "") -> list[RssFeedItem]: ...


def rss_source_id(node: WorkflowNode) -> str | None:
    """Resolve the intended feed from creator-produced node language."""
    text = " ".join((node.name, node.description, node.instructions)).casefold()
    if "rss" not in text and "news" not in text:
        return None
    if "youtube" in text:
        return "youtube"
    if (
        "web_xml" in text
        or "xml source" in text
        or ("web" in text and "xml" in text)
    ):
        return "web_xml"
    if "source x" in text or "rss x" in text or "twitter" in text:
        return "x"
    if "news" in text:
        return "news"
    return "rss"


class NewsApiError(RuntimeError):
    pass


class NewsApiSource:
    """Live NewsAPI adapter normalized to the workflow's RSS item contract."""

    _RELATED_QUERY_BY_TOPIC = {
        "ic markets": '(forex OR CFD) AND (broker OR "trading platform")',
    }
    _QUERY_STOP_WORDS = {
        "a", "an", "and", "about", "articles", "for", "from", "get", "give",
        "headlines", "in", "latest", "me", "news", "of", "on", "recent", "search",
        "show", "the", "to", "with",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsapi.org/v2",
        timeout_seconds: float = 15.0,
        page_size: int = 10,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size
        self._cache: dict[str, tuple[float, list[dict[str, Any]], bool]] = {}
        self._search_lock = asyncio.Lock()

    @staticmethod
    def _topic_from(query: str) -> str:
        value = " ".join(query.strip().split())
        if not value:
            return ""
        quoted = re.search(r'["“]([^"”]{2,120})["”]', value)
        if quoted:
            return quoted.group(1).strip()
        value = re.split(
            r"\s+(?:and|then|before|after)\s+(?:summari[sz]e|write|report|send|publish|post|compare|analyse|analyze)\b",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        about = re.search(
            r"\b(?:about|on|for(?!\s+(?:the\s+)?(?:last|past|previous)\b))\s+(.+)$",
            value,
            re.IGNORECASE,
        )
        if about:
            value = about.group(1)
        value = re.sub(
            r"\s+(?:for|from|during|within|in)\s+(?:the\s+)?(?:last|past|previous)\s+\d+\s+(?:hours?|days?|weeks?|months?)\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\s+(?:from|on|during|for|in)\s+(?:today|yesterday|this\s+(?:week|month)|20\d{2})\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"^(?:please\s+)?(?:(?:find|search(?:\s+for)?|get|fetch|collect|show|give\s+me)\s+)?(?:(?:the|latest|recent|current|today(?:'s)?)\s+)*(?:news|articles|headlines)?\s*(?:about|on|for)?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"\s+(?:news|articles|headlines)\s*$", "", value, flags=re.IGNORECASE)
        return value.strip(" .,:;!?-")[:180]

    @staticmethod
    def _from_for(query: str) -> str | None:
        now = datetime.now(timezone.utc)
        relative = re.search(
            r"\b(?:last|past|previous)\s+(\d{1,3})\s+(hours?|days?|weeks?|months?)\b",
            query,
            re.IGNORECASE,
        )
        if relative:
            amount = min(int(relative.group(1)), 365)
            unit = relative.group(2).casefold()
            if unit.startswith("hour"):
                start = now - timedelta(hours=amount)
            elif unit.startswith("week"):
                start = now - timedelta(weeks=amount)
            elif unit.startswith("month"):
                start = now - timedelta(days=amount * 30)
            else:
                start = now - timedelta(days=amount)
            return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if re.search(r"\btoday(?:'s)?\b", query, re.IGNORECASE):
            return now.date().isoformat()
        if re.search(r"\byesterday\b", query, re.IGNORECASE):
            return (now - timedelta(days=1)).date().isoformat()
        if re.search(r"\b(?:latest|recent|current)\b", query, re.IGNORECASE):
            return (now - timedelta(days=30)).date().isoformat()
        return None

    @classmethod
    def _topic_terms(cls, topic: str) -> list[str]:
        return [
            term.casefold()
            for term in re.findall(r"[\w'-]+", topic, flags=re.UNICODE)
            if term.casefold() not in cls._QUERY_STOP_WORDS
        ]

    @classmethod
    def _boolean_query(cls, topic: str) -> str:
        terms = cls._topic_terms(topic)
        if len(terms) < 2 or any(len(term) <= 2 for term in terms):
            return f'"{topic}"' if " " in topic else f"+{topic}"
        return " AND ".join(f'"{term}"' if " " in term else f"+{term}" for term in terms)

    def build_search_plan(self, query: str) -> dict[str, Any]:
        """Turn natural workflow input into an inspectable NewsAPI request plan."""
        topic = self._topic_from(query)
        if not topic:
            return {
                "kind": "news_search_plan",
                "raw_input": query,
                "topic": "",
                "endpoint": "/top-headlines",
                "params": {
                    "country": "us",
                    "category": "business",
                    "pageSize": self.page_size,
                    "page": 1,
                },
                "broad_params": None,
            }
        exact_params: dict[str, Any] = {
            "q": f'"{topic}"' if " " in topic else f"+{topic}",
            "searchIn": "title,description",
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": self.page_size,
            "page": 1,
        }
        from_date = self._from_for(query)
        if from_date:
            exact_params["from"] = from_date
        broad_params = {**exact_params, "q": self._boolean_query(topic)}
        broad_params.pop("searchIn", None)
        return {
            "kind": "news_search_plan",
            "raw_input": query,
            "topic": topic,
            "endpoint": "/everything",
            "params": exact_params,
            "broad_params": broad_params,
        }

    def _decode_search_plan(self, value: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("kind") != "news_search_plan":
            return None
        params = payload.get("params")
        if not isinstance(params, dict):
            return None
        return payload

    def _request_for(self, query: str, *, broad: bool = False) -> tuple[str, dict[str, Any]]:
        plan = self._decode_search_plan(query)
        if plan:
            params = plan.get("broad_params") if broad else plan["params"]
            if broad and not isinstance(params, dict):
                params = plan["params"]
            return str(plan.get("endpoint") or "/everything"), dict(params)
        topic = self._topic_from(query)
        common: dict[str, Any] = {"pageSize": self.page_size, "page": 1}
        if not topic:
            return "/top-headlines", {**common, "country": "us", "category": "business"}
        news_query = self._boolean_query(topic) if broad else (f'"{topic}"' if " " in topic else f"+{topic}")
        params: dict[str, Any] = {
            **common,
            "q": news_query,
            "language": "en",
            "sortBy": "relevancy",
        }
        from_date = self._from_for(query)
        if from_date:
            params["from"] = from_date
        if not broad:
            params["searchIn"] = "title,description"
        return "/everything", params

    def _related_request_for(self, topic: str, query: str = "") -> tuple[str, dict[str, Any]] | None:
        expanded_query = self._RELATED_QUERY_BY_TOPIC.get(topic.casefold())
        if not expanded_query:
            return None
        params: dict[str, Any] = {
            "pageSize": self.page_size,
            "page": 1,
            "q": expanded_query,
            "language": "en",
            "sortBy": "relevancy",
        }
        from_date = self._from_for(query)
        if from_date:
            params["from"] = from_date
        return "/everything", params

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers={"X-Api-Key": self.api_key},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("message")
            except Exception:
                detail = None
            raise NewsApiError(detail or f"NewsAPI returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise NewsApiError(f"NewsAPI request failed: {exc}") from exc
        if payload.get("status") != "ok":
            raise NewsApiError(payload.get("message") or "NewsAPI returned an error response.")
        return payload

    @staticmethod
    def _article_matches_topic(article: dict[str, Any], topic: str) -> bool:
        if not topic:
            return True
        haystack = " ".join(str(article.get(field) or "") for field in ("title", "description", "content")).casefold()
        phrase = topic.casefold()
        if " " in phrase and (
            phrase in haystack
            or re.sub(r"\W+", "", phrase) in re.sub(r"\W+", "", haystack)
        ):
            return True
        if " " not in phrase and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack):
            return True
        terms = NewsApiSource._topic_terms(topic)
        if len(terms) < 2 or any(len(term) <= 2 for term in terms):
            return False
        return all(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack) for term in terms)

    @staticmethod
    def _article_score(article: dict[str, Any], topic: str, related: bool) -> float:
        title = str(article.get("title") or "").casefold()
        description = str(article.get("description") or "").casefold()
        content = str(article.get("content") or "").casefold()
        phrase = topic.casefold()
        score = 0.0
        if phrase and phrase in title:
            score += 100
        if phrase and phrase in description:
            score += 60
        if phrase and phrase in content:
            score += 30
        if related:
            score += sum(
                term in f"{title} {description} {content}"
                for term in ("forex", "cfd", "broker", "trading platform")
            ) * 15
        published = article.get("publishedAt")
        if published:
            try:
                age_days = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(published).replace("Z", "+00:00"))).days)
                score += max(0, 15 - min(age_days, 15))
            except ValueError:
                pass
        if article.get("url"):
            score += 2
        return score

    def _rank_dedupe_and_diversify(
        self,
        articles: list[dict[str, Any]],
        topic: str,
        related: bool,
    ) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for article in sorted(
            articles,
            key=lambda item: self._article_score(item, topic, related),
            reverse=True,
        ):
            url_key = re.sub(r"[?#].*$", "", str(article.get("url") or "")).casefold()
            title_key = re.sub(r"\W+", "", str(article.get("title") or "")).casefold()
            key = url_key or title_key
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(article)

        selected: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        publisher_counts: dict[str, int] = {}
        for article in unique:
            publisher = str((article.get("source") or {}).get("name") or "unknown").casefold()
            if publisher_counts.get(publisher, 0) >= 2:
                deferred.append(article)
                continue
            selected.append(article)
            publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
            if len(selected) == self.page_size:
                return selected
        selected.extend(deferred[: self.page_size - len(selected)])
        return selected

    async def _search_articles(self, query: str) -> tuple[str, list[dict[str, Any]], bool]:
        plan = self._decode_search_plan(query)
        raw_query = str(plan.get("raw_input") or "") if plan else query
        topic = str(plan.get("topic") or "") if plan else self._topic_from(query)
        from_date = (plan.get("params") or {}).get("from") if plan else self._from_for(query)
        cache_key = f"{topic.casefold()}|{from_date or 'all'}" if topic else "__headlines__"
        async with self._search_lock:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > time.monotonic():
                return topic, list(cached[1]), cached[2]

            path, params = self._request_for(query)
            payload = await self._request(path, params)
            articles = [
                article for article in payload.get("articles") or []
                if self._article_matches_topic(article, topic)
            ]
            if topic and not articles:
                path, params = self._request_for(query, broad=True)
                payload = await self._request(path, params)
                articles = [
                    article for article in payload.get("articles") or []
                    if self._article_matches_topic(article, topic)
                ]
            related_coverage = False
            if topic and not articles:
                related_request = self._related_request_for(topic, raw_query)
                if related_request:
                    path, params = related_request
                    payload = await self._request(path, params)
                    articles = list(payload.get("articles") or [])
                    related_coverage = True
            articles = self._rank_dedupe_and_diversify(articles, topic, related_coverage)
            self._cache[cache_key] = (time.monotonic() + 120, list(articles), related_coverage)
            return topic, articles, related_coverage

    async def fetch(self, node: WorkflowNode, query: str = "") -> list[RssFeedItem]:
        source = rss_source_id(node) or "news"
        topic, articles, related_coverage = await self._search_articles(query)
        items: list[RssFeedItem] = []
        for article in articles:
            title = article.get("title")
            link = article.get("url")
            published = article.get("publishedAt")
            if not title and not link:
                continue
            publisher = (article.get("source") or {}).get("name")
            description = article.get("description") or article.get("content") or ""
            if related_coverage:
                description = f"Related industry coverage (no direct {topic} match): {description}"
            items.append(
                RssFeedItem(
                    source=source,
                    title=title or "Untitled article",
                    link=link or "",
                    pub_date=published or "",
                    description=description,
                    uncertain=related_coverage or not bool(title and link and published),
                    publisher=publisher,
                    author=article.get("author"),
                    image_url=article.get("urlToImage"),
                    content=article.get("content"),
                    match_type="related" if related_coverage else "direct",
                    query_topic=topic or None,
                )
            )
        return items


class MockRssSource:
    """Deterministic POC feed. Replace this adapter when providers are selected."""

    _ITEMS: dict[str, tuple[RssFeedItem, ...]] = {
        "youtube": (
            RssFeedItem(
                source="youtube",
                title="Building reliable multi-agent workflows",
                link="https://www.youtube.com/watch?v=mock-agent-workflows",
                pub_date="2026-08-19T08:30:00Z",
                description="A practical walkthrough of parallel agents, validation, and retry boundaries.",
            ),
            RssFeedItem(
                source="youtube",
                title="LangGraph execution patterns explained",
                link="https://www.youtube.com/watch?v=mock-langgraph-patterns",
                pub_date="2026-08-18T15:00:00Z",
                description="An overview of fan-out, fan-in, routing, and durable workflow state.",
            ),
        ),
        "x": (
            RssFeedItem(
                source="x",
                title="Agent observability checklist",
                link="https://x.com/mock/status/1000000000000000001",
                pub_date="2026-08-19T09:10:00Z",
                description="Trace every model call, tool execution, latency, error, and workflow run identifier.",
            ),
            RssFeedItem(
                source="x",
                title="Why workflow validation belongs before execution",
                link="https://x.com/mock/status/1000000000000000002",
                pub_date="2026-08-19T07:45:00Z",
                description="Validate graph topology and required configuration before any agent starts.",
            ),
        ),
        "web_xml": (
            RssFeedItem(
                source="web_xml",
                title="Designing provider-agnostic automation systems",
                link="https://example.com/mock/provider-agnostic-automation",
                pub_date="2026-08-18T12:00:00Z",
                description="Use narrow adapters so mock RSS, live RSS, and search providers can be swapped safely.",
            ),
            RssFeedItem(
                source="web_xml",
                title="Testing complex workflow graphs",
                link="https://example.com/mock/testing-workflow-graphs",
                pub_date="2026-08-17T10:20:00Z",
                description="Test parallel branches, joins, routers, failures, and empty-source behavior independently.",
            ),
        ),
        "rss": (
            RssFeedItem(
                source="rss",
                title="Mock RSS item",
                link="https://example.com/mock/rss-item",
                pub_date="2026-08-19T08:00:00Z",
                description="A fallback item for a generic RSS trigger during the proof of concept.",
            ),
        ),
    }

    async def fetch(self, node: WorkflowNode, query: str = "") -> list[RssFeedItem]:
        source = rss_source_id(node) or "rss"
        return list(self._ITEMS.get(source, self._ITEMS["rss"]))


class RssTriggerExecutor:
    def __init__(self, source: RssSource | None = None):
        self.source = source or create_rss_source()

    @property
    def provider_name(self) -> str:
        return "newsapi" if isinstance(self.source, NewsApiSource) else "mock"

    def supports(self, node: WorkflowNode, *, is_root: bool = False) -> bool:
        return rss_source_id(node) is not None and (node.type == "trigger" or is_root)

    async def execute(self, node: WorkflowNode, query: str = "") -> str:
        items = await self.source.fetch(node, query)
        return json.dumps([asdict(item) for item in items], ensure_ascii=False)

    def plan_query(self, query: str) -> str:
        if isinstance(self.source, NewsApiSource):
            return json.dumps(self.source.build_search_plan(query), ensure_ascii=False)
        return json.dumps(
            {
                "kind": "news_search_plan",
                "raw_input": query,
                "topic": NewsApiSource._topic_from(query),
                "endpoint": "mock",
                "params": {},
                "broad_params": None,
            },
            ensure_ascii=False,
        )


def create_rss_source() -> RssSource:
    if settings.news_api_key.strip():
        return NewsApiSource(
            api_key=settings.news_api_key,
            base_url=settings.news_api_base_url,
            timeout_seconds=settings.news_api_timeout_seconds,
            page_size=settings.news_api_page_size,
        )
    return MockRssSource()
