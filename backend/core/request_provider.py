from __future__ import annotations

from fastapi import Header

from libs.langchain.provider import BaseAIProvider, create_request_provider


def get_request_provider(
    api_key: str | None = Header(default=None, alias="X-Nodara-LLM-Key"),
    base_url: str | None = Header(default=None, alias="X-Nodara-LLM-URL"),
    model: str | None = Header(default=None, alias="X-Nodara-LLM-Model"),
) -> BaseAIProvider:
    return create_request_provider(api_key=api_key, base_url=base_url, model=model)
