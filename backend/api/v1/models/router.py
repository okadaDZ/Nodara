import httpx
from fastapi import APIRouter, Header

from libs.langchain.model_catalog import ModelCatalogResponse, get_model_catalog
from libs.langchain.model_catalog import AvailableModel
from core.settings import settings

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelCatalogResponse)
async def list_models(
    api_key: str | None = Header(default=None, alias="X-Nodara-LLM-Key"),
    base_url: str | None = Header(default=None, alias="X-Nodara-LLM-URL"),
    model: str | None = Header(default=None, alias="X-Nodara-LLM-Model"),
) -> ModelCatalogResponse:
    if api_key or base_url or model:
        default_model = model or settings.llm_model
        model_ids = {default_model}
        resolved_key = api_key or settings.llm_api_key
        if resolved_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(
                        f"{(base_url or settings.llm_base_url).rstrip('/')}/models",
                        headers={"Authorization": f"Bearer {resolved_key}"},
                    )
                    response.raise_for_status()
                model_ids.update(
                    item["id"] for item in response.json().get("data", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                )
            except Exception:
                pass
        ordered = [default_model] + sorted(model_ids - {default_model})
        return ModelCatalogResponse(
            default_model=default_model,
            models=[AvailableModel(id=model_id, name=model_id) for model_id in ordered],
        )
    return await get_model_catalog()
