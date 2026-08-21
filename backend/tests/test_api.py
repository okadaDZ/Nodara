from __future__ import annotations

import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_model_catalog_exposes_default_and_available_models(client: AsyncClient):
    response = await client.get("/api/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["default_model"] in {model["id"] for model in payload["models"]}
    assert (await client.get("/api/v1/models")).status_code == 200


@pytest.mark.asyncio
async def test_model_catalog_accepts_request_scoped_global_model(client: AsyncClient):
    response = await client.get("/api/models", headers={"X-Nodara-LLM-Model": "local-model"})
    assert response.status_code == 200
    assert response.json()["default_model"] == "local-model"
    assert response.json()["models"][0]["id"] == "local-model"


@pytest.mark.asyncio
async def test_create_workflow_from_text(client: AsyncClient):
    payload = {"text": "I want an agent to search AI news and another to write a post"}
    response = await client.post("/api/workflows/from-text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "workflow" in data
    wf = data["workflow"]
    assert "id" in wf
    assert wf["enabled"] is True
    assert len(wf["nodes"]) >= 2
    assert len(wf["edges"]) >= 1

    # Test get workflow
    get_res = await client.get(f"/api/workflows/{wf['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["workflow"]["id"] == wf["id"]

    # Test list workflows
    list_res = await client.get("/api/workflows")
    assert list_res.status_code == 200
    summaries = list_res.json()["workflows"]
    assert any(s["id"] == wf["id"] for s in summaries)
    assert next(s for s in summaries if s["id"] == wf["id"])["enabled"] is True


@pytest.mark.asyncio
async def test_workflow_can_be_disabled_and_cannot_run(client: AsyncClient):
    create_res = await client.post(
        "/api/workflows/from-text",
        json={"text": "Research a topic and summarize it"},
    )
    workflow = create_res.json()["workflow"]

    toggle_res = await client.patch(
        f"/api/workflows/{workflow['id']}/enabled",
        json={"enabled": False},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["workflow"]["enabled"] is False

    list_res = await client.get("/api/workflows")
    summary = next(item for item in list_res.json()["workflows"] if item["id"] == workflow["id"])
    assert summary["enabled"] is False

    run_res = await client.post(
        f"/api/workflows/{workflow['id']}/run",
        json={"input": "Run it"},
    )
    assert run_res.status_code == 409
    assert "turned off" in run_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_workflow_can_be_renamed_without_replacing_its_graph(client: AsyncClient):
    create_res = await client.post(
        "/api/workflows/from-text",
        json={"text": "Research a topic and summarize it"},
    )
    workflow = create_res.json()["workflow"]

    rename_res = await client.patch(
        f"/api/workflows/{workflow['id']}/name",
        json={"name": "  Morning Research Brief  "},
    )
    assert rename_res.status_code == 200
    renamed = rename_res.json()["workflow"]
    assert renamed["name"] == "Morning Research Brief"
    assert renamed["nodes"] == workflow["nodes"]
    assert renamed["edges"] == workflow["edges"]

    list_res = await client.get("/api/workflows")
    summary = next(item for item in list_res.json()["workflows"] if item["id"] == workflow["id"])
    assert summary["name"] == "Morning Research Brief"

    blank_res = await client.patch(
        f"/api/workflows/{workflow['id']}/name",
        json={"name": "   "},
    )
    assert blank_res.status_code == 422


@pytest.mark.asyncio
async def test_offline_image_workflow_defaults_to_complex_parallel_graph(client: AsyncClient):
    response = await client.post(
        "/api/workflows/from-image",
        files={"image": ("diagram.jpg", b"mock-image-content", "image/jpeg")},
    )

    assert response.status_code == 200
    workflow = response.json()["workflow"]
    assert len(workflow["nodes"]) == 15
    assert len(workflow["edges"]) == 18
    assert sum(edge["source"] == "intake" for edge in workflow["edges"]) == 4
    assert sum(edge["target"] == "critic" for edge in workflow["edges"]) == 3
    critic = next(node for node in workflow["nodes"] if node["id"] == "critic")
    assert "at most 3 passes" in critic["instructions"]
    assert {node["type"] for node in workflow["nodes"]} >= {
        "trigger", "agent", "condition", "output", "tool", "memory", "parser"
    }
    assert {edge["kind"] for edge in workflow["edges"]} >= {
        "flow", "conditional", "tool", "memory", "parser"
    }


@pytest.mark.asyncio
async def test_image_workflow_job_reports_progress_and_returns_saved_result(client: AsyncClient):
    start = await client.post(
        "/api/workflows/from-image/jobs",
        files={"image": ("diagram.jpg", b"mock-image-content", "image/jpeg")},
    )
    assert start.status_code == 202
    job_id = start.json()["job_id"]

    payload = None
    for _ in range(30):
        status_response = await client.get(f"/api/workflows/from-image/jobs/{job_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert payload["stage"] in {
            "queued", "read_diagram", "build_graph", "finalize_workflow", "complete"
        }
        if payload["status"] == "completed":
            break
        await asyncio.sleep(0.01)

    assert payload is not None
    assert payload["status"] == "completed"
    assert payload["stage"] == "complete"
    assert payload["result"]["workflow"]["id"]
    saved = await client.get(f"/api/workflows/{payload['result']['workflow']['id']}")
    assert saved.status_code == 200


@pytest.mark.asyncio
async def test_generate_agent_instructions_endpoint(client: AsyncClient):
    create_res = await client.post(
        "/api/workflows/from-text",
        json={"text": "Research Dubai restaurants and recommend the best 3"},
    )
    assert create_res.status_code == 200
    wf = create_res.json()["workflow"]
    node_id = wf["nodes"][0]["id"]

    gen_res = await client.post(
        f"/api/workflows/{wf['id']}/nodes/{node_id}/generate",
        json={"user_hint": "Focus on high rating"},
    )
    assert gen_res.status_code == 200
    assert "instructions" in gen_res.json()
    assert len(gen_res.json()["instructions"]) > 0


@pytest.mark.asyncio
async def test_run_workflow_endpoint(client: AsyncClient):
    create_res = await client.post(
        "/api/workflows/from-text",
        json={"text": "Summarize today's tech news"},
    )
    assert create_res.status_code == 200
    wf = create_res.json()["workflow"]

    run_res = await client.post(
        f"/api/workflows/{wf['id']}/run",
        json={"input": "Latest AI news in 2026"},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["workflow_id"] == wf["id"]
    assert "id" in run_data

    # Check run status endpoint
    status_res = await client.get(f"/api/runs/{run_data['id']}")
    assert status_res.status_code == 200
    assert status_res.json()["id"] == run_data["id"]

    # Allow background execution to progress and check again
    await asyncio.sleep(0.1)
    status_res_after = await client.get(f"/api/runs/{run_data['id']}")
    assert status_res_after.status_code == 200
    assert status_res_after.json()["id"] == run_data["id"]
