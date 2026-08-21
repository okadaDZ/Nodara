from __future__ import annotations

import asyncio
import logging
import time

import httpx
from pydantic import BaseModel

from core.settings import settings

logger = logging.getLogger(__name__)


class AvailableModel(BaseModel):
    id: str
    name: str


class ModelCatalogResponse(BaseModel):
    default_model: str
    models: list[AvailableModel]


class ModelCatalog:
    """Fetch the provider's model list, with a safe configured fallback."""

    def __init__(self) -> None:
        self._cached: ModelCatalogResponse | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()

    def _configured_ids(self) -> set[str]:
        return {model for model in (settings.llm_model, settings.vision_model) if model}

    async def get(self) -> ModelCatalogResponse:
        now = time.monotonic()
        if self._cached and now - self._cached_at < settings.models_cache_ttl_seconds:
            return self._cached

        async with self._lock:
            now = time.monotonic()
            if self._cached and now - self._cached_at < settings.models_cache_ttl_seconds:
                return self._cached

            model_ids = self._configured_ids()
            if settings.llm_api_key:
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(
                            f"{settings.llm_base_url.rstrip('/')}/models",
                            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                        )
                        response.raise_for_status()
                    model_ids.update(
                        item["id"] for item in response.json().get("data", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    )
                except Exception as exc:
                    logger.warning("Could not refresh provider model catalog: %s", exc)

            ordered_ids = [settings.llm_model] + sorted(model_ids - {settings.llm_model})
            self._cached = ModelCatalogResponse(
                default_model=settings.llm_model,
                models=[AvailableModel(id=model_id, name=model_id) for model_id in ordered_ids if model_id],
            )
            self._cached_at = now
            return self._cached


model_catalog = ModelCatalog()


async def get_model_catalog() -> ModelCatalogResponse:
    return await model_catalog.get()
