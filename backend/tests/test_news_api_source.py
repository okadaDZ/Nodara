from __future__ import annotations

import json
import pytest

from libs.models.workflow import WorkflowNode
from libs.runtime.rss_source import NewsApiError, NewsApiSource, RssTriggerExecutor


class StubNewsApiSource(NewsApiSource):
    def __init__(self, payload):
        super().__init__(api_key="test-key")
        self.payload = payload
        self.requests = []

    async def _request(self, path, params):
        self.requests.append((path, params))
        if self.payload.get("status") != "ok":
            raise NewsApiError(self.payload.get("message", "error"))
        return self.payload


class SequenceNewsApiSource(NewsApiSource):
    def __init__(self, payloads):
        super().__init__(api_key="test-key")
        self.payloads = list(payloads)
        self.requests = []

    async def _request(self, path, params):
        self.requests.append((path, params))
        return self.payloads.pop(0)


@pytest.mark.asyncio
async def test_newsapi_maps_business_headlines_to_rss_contract() -> None:
    source = StubNewsApiSource({
        "status": "ok",
        "articles": [{
            "source": {"id": None, "name": "Example News"},
            "author": "Reporter",
            "title": "Markets move on new launch",
            "description": "Business headline description.",
            "url": "https://example.com/article",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2026-08-19T07:02:57Z",
            "content": "Article preview",
        }],
    })

    items = await source.fetch(WorkflowNode(type="trigger", name="RSS X"))

    assert source.requests == [("/top-headlines", {
        "pageSize": 10, "page": 1, "country": "us", "category": "business"
    })]
    assert items[0].source == "x"
    assert items[0].publisher == "Example News"
    assert items[0].link == "https://example.com/article"
    assert items[0].pub_date == "2026-08-19T07:02:57Z"
    assert items[0].uncertain is False


@pytest.mark.asyncio
async def test_newsapi_uses_exact_topic_search_for_workflow_input() -> None:
    source = StubNewsApiSource({
        "status": "ok",
        "articles": [{
            "title": "IC Markets expands its trading platform",
            "description": "The broker announced an update.",
            "url": "https://example.com/ic-markets",
            "publishedAt": "2026-08-19T07:02:57Z",
        }],
    })
    items = await source.fetch(
        WorkflowNode(type="trigger", name="RSS Web (XML)"),
        "Find recent news about IC Markets and summarize it",
    )
    path, params = source.requests[0]
    assert path == "/everything"
    assert params["q"] == '"IC Markets"'
    assert params["searchIn"] == "title,description"
    assert params["sortBy"] == "relevancy"
    assert params["language"] == "en"
    assert items[0].title.startswith("IC Markets")


@pytest.mark.asyncio
async def test_newsapi_broadens_to_content_but_rejects_unrelated_results() -> None:
    source = StubNewsApiSource({
        "status": "ok",
        "articles": [{
            "title": "Global stocks rise",
            "description": "Major indexes moved higher.",
            "content": "No company-specific coverage.",
            "url": "https://example.com/markets",
            "publishedAt": "2026-08-19T07:02:57Z",
        }],
    })
    items = await source.fetch(WorkflowNode(type="trigger", name="RSS X"), "Acme Rocket Labs")
    assert len(source.requests) == 2
    assert source.requests[0][1]["searchIn"] == "title,description"
    assert "searchIn" not in source.requests[1][1]
    assert items == []


@pytest.mark.asyncio
async def test_newsapi_returns_clearly_marked_related_coverage_for_ic_markets() -> None:
    empty = {"status": "ok", "articles": []}
    related = {
        "status": "ok",
        "articles": [{
            "title": "Broker launches improved forex trading platform",
            "description": "An online broker expanded its trading tools.",
            "url": "https://example.com/forex-broker",
            "publishedAt": "2026-08-19T07:02:57Z",
        }],
    }
    source = SequenceNewsApiSource([empty, empty, related])

    items = await source.fetch(WorkflowNode(type="trigger", name="RSS Web XML"), "IC Markets")

    assert source.requests[2][1]["q"] == '(forex OR CFD) AND (broker OR "trading platform")'
    assert len(items) == 1
    assert items[0].uncertain is True
    assert items[0].match_type == "related"
    assert items[0].query_topic == "IC Markets"
    assert items[0].description.startswith("Related industry coverage (no direct IC Markets match):")


@pytest.mark.asyncio
async def test_newsapi_pipeline_deduplicates_diversifies_and_caches_parallel_queries() -> None:
    articles = [
        {
            "source": {"name": "Publisher A"},
            "title": "IC Markets launches a new platform",
            "description": "IC Markets product news.",
            "url": "https://example.com/one?tracking=1",
            "publishedAt": "2026-08-19T07:02:57Z",
        },
        {
            "source": {"name": "Publisher A"},
            "title": "IC Markets launches a new platform",
            "description": "Duplicate syndication.",
            "url": "https://example.com/one?tracking=2",
            "publishedAt": "2026-08-19T07:02:57Z",
        },
        {
            "source": {"name": "Publisher B"},
            "title": "Interview with IC Markets",
            "description": "IC Markets company interview.",
            "url": "https://example.org/two",
            "publishedAt": "2026-08-18T07:02:57Z",
        },
    ]
    source = StubNewsApiSource({"status": "ok", "articles": articles})
    first = await source.fetch(WorkflowNode(type="trigger", name="RSS X"), "IC Markets")
    second = await source.fetch(WorkflowNode(type="trigger", name="RSS Web XML"), "IC Markets")

    assert len(source.requests) == 1
    assert len(first) == 2
    assert {item.publisher for item in first} == {"Publisher A", "Publisher B"}
    assert all(item.match_type == "direct" for item in first)
    assert [item.title for item in second] == [item.title for item in first]
    assert {item.source for item in second} == {"web_xml"}


@pytest.mark.asyncio
async def test_newsapi_errors_are_not_replaced_with_fake_live_results() -> None:
    source = StubNewsApiSource({"status": "error", "message": "Rate limit reached"})
    with pytest.raises(NewsApiError, match="Rate limit reached"):
        await source.fetch(WorkflowNode(type="trigger", name="News"))


def test_root_rss_agent_is_source_but_downstream_rss_processor_is_not() -> None:
    executor = RssTriggerExecutor(source=StubNewsApiSource({"status": "ok", "articles": []}))
    legacy_root = WorkflowNode(type="agent", name="RSS YouTube Source")
    downstream = WorkflowNode(type="agent", name="RSS Normalizer")
    assert executor.supports(legacy_root, is_root=True)
    assert not executor.supports(legacy_root, is_root=False)
    assert not executor.supports(downstream, is_root=False)


@pytest.mark.parametrize(
    ("request_text", "topic"),
    [
        ("Get me news on IC Markets for the last 24 hours", "IC Markets"),
        ("Latest AI news in 2026", "AI"),
        ("Find recent news about Tesla and summarize it", "Tesla"),
        ('Search for "artificial intelligence regulation" today', "artificial intelligence regulation"),
    ],
)
def test_newsapi_extracts_topic_without_time_or_workflow_instructions(request_text: str, topic: str) -> None:
    assert NewsApiSource._topic_from(request_text) == topic


def test_newsapi_uses_documented_iso_time_window_and_boolean_fallback() -> None:
    source = NewsApiSource(api_key="test-key")
    _, exact = source._request_for("News about renewable energy for the last 24 hours")
    _, broad = source._request_for("News about renewable energy for the last 24 hours", broad=True)

    assert exact["q"] == '"renewable energy"'
    assert exact["from"].endswith("Z")
    assert "T" in exact["from"]
    assert exact["searchIn"] == "title,description"
    assert broad["q"] == "+renewable AND +energy"
    assert "searchIn" not in broad


def test_newsapi_does_not_accept_short_acronym_token_as_company_match() -> None:
    unrelated = {
        "title": "Markets rally after semiconductor update",
        "description": "An IC supplier reported higher revenue.",
        "content": "Global markets moved higher.",
    }
    assert not NewsApiSource._article_matches_topic(unrelated, "IC Markets")


def test_newsapi_matches_short_acronyms_as_whole_words_only() -> None:
    assert NewsApiSource._article_matches_topic(
        {"title": "AI regulation advances", "description": "New rules"},
        "AI",
    )
    assert not NewsApiSource._article_matches_topic(
        {"title": "Retail markets advance", "description": "Daily update"},
        "AI",
    )


def test_newsapi_keeps_time_window_on_related_coverage_request() -> None:
    source = NewsApiSource(api_key="test-key")
    request = source._related_request_for("IC Markets", "IC Markets for the last 24 hours")
    assert request is not None
    _, params = request
    assert params["from"].endswith("Z")


@pytest.mark.asyncio
async def test_newsapi_consumes_structured_query_plan_from_planner_node() -> None:
    payload = {
        "status": "ok",
        "articles": [{
            "title": "Tesla expands charging network",
            "description": "Tesla added new charging locations.",
            "url": "https://example.com/tesla",
            "publishedAt": "2026-08-19T07:02:57Z",
        }],
    }
    source = StubNewsApiSource(payload)
    plan = source.build_search_plan("Latest Tesla news for the last 7 days")

    items = await source.fetch(
        WorkflowNode(type="trigger", name="News search"),
        json.dumps(plan),
    )

    assert source.requests[0][0] == "/everything"
    assert source.requests[0][1]["q"] == "+Tesla"
    assert source.requests[0][1]["from"].endswith("Z")
    assert items[0].query_topic == "Tesla"
