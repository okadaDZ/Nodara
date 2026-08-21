from __future__ import annotations

import uuid
from typing import Any

from libs.models.workflow import Workflow, WorkflowNode
from libs.runtime.rss_source import rss_source_id


# n8n LangChain agent node type
_N8N_AGENT_TYPE = "@n8n/n8n-nodes-langchain.agent"
_N8N_OPENAI_MODEL_TYPE = "@n8n/n8n-nodes-langchain.lmChatOpenAi"
_N8N_MANUAL_TRIGGER_TYPE = "n8n-nodes-base.manualTrigger"
_N8N_CODE_TYPE = "n8n-nodes-base.code"
_N8N_HTTP_REQUEST_TYPE = "n8n-nodes-base.httpRequest"

_GRID_X_START = 240
_GRID_Y_START = 300
_GRID_X_STEP = 420  # horizontal gap between chained agents
_GRID_Y_STEP = 400  # vertical gap between parallel agents and their model nodes
_SUPPORT_TYPES = {"tool", "memory", "parser"}


def _node_id() -> str:
    return str(uuid.uuid4())


def _agent_n8n_node(
    node: WorkflowNode,
    x: float,
    y: float,
) -> dict[str, Any]:
    """Map a WorkflowNode agent to an n8n LangChain Agent node."""
    return {
        "id": _node_id(),
        "name": node.name,
        "type": _N8N_AGENT_TYPE,
        "typeVersion": 1.7,
        "position": [round(x), round(y)],
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.input ?? $json.output ?? $json.text ?? '' }}",
            "options": {
                "systemMessage": node.instructions or node.description or f"You are a {node.name} agent.",
            },
        },
    }


def _openai_model_node(agent_name: str, model_name: str, x: float, y: float) -> dict[str, Any]:
    """Create an OpenAI Chat Model sub-node attached to the agent."""
    return {
        "id": _node_id(),
        "name": f"OpenAI Chat Model ({agent_name})",
        "type": _N8N_OPENAI_MODEL_TYPE,
        "typeVersion": 1.2,
        "position": [round(x), round(y + 200)],
        "parameters": {
            "model": model_name,
            "options": {},
        },
        "credentials": {
            "openAiApi": {
                "id": "openai",
                "name": "OpenAI account",
            }
        },
    }


def _newsapi_http_node(node: WorkflowNode, x: float, y: float) -> dict[str, Any]:
    """Export a news/RSS source as an executable external API call, not an LLM."""
    return {
        "id": _node_id(),
        "name": node.name,
        "type": _N8N_HTTP_REQUEST_TYPE,
        "typeVersion": 4.2,
        "position": [round(x), round(y)],
        "parameters": {
            "url": "https://newsapi.org/v2/everything",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {
                        "name": "q",
                        "value": "={{ $json.params?.q ?? ('\"' + ($json.input ?? $json.query ?? '') + '\"') }}",
                    },
                    {"name": "searchIn", "value": "title,description"},
                    {"name": "from", "value": "={{ $json.params?.from ?? $now.minus({ days: 30 }).toISODate() }}"},
                    {"name": "language", "value": "en"},
                    {"name": "sortBy", "value": "relevancy"},
                    {"name": "pageSize", "value": "10"},
                ]
            },
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "X-Api-Key", "value": "={{ $env.NEWS_API_KEY }}"},
                ]
            },
            "options": {
                "response": {"response": {"neverError": False, "responseFormat": "json"}},
            },
        },
        "notes": "Set NEWS_API_KEY in the n8n environment before running this workflow.",
    }


def _query_builder_n8n_node(node: WorkflowNode, x: float, y: float) -> dict[str, Any]:
    """Export the deterministic search planner as an n8n Code node."""
    code = """const raw = String($json.input ?? $json.query ?? '').trim();
let topic = raw
  .replace(/\\s+(and|then)\\s+(summarize|summarise|write|report|send|publish|post).*$/i, '')
  .replace(/^\\s*(please\\s+)?(find|search(\\s+for)?|get|fetch|collect|show|give\\s+me)?\\s*(the|latest|recent|current|today's)?\\s*(news|articles|headlines)?\\s*(about|on|for)?\\s*/i, '')
  .replace(/\\s+(for|from|during|within|in)\\s+(the\\s+)?(last|past|previous)\\s+\\d+\\s+(hours?|days?|weeks?|months?).*$/i, '')
  .replace(/\\s+(news|articles|headlines)\\s*$/i, '')
  .trim();
const quoted = raw.match(/[\"“]([^\"”]{2,120})[\"”]/);
if (quoted) topic = quoted[1].trim();
const params = {
  q: topic.includes(' ') ? `\"${topic}\"` : `+${topic}`,
  searchIn: 'title,description',
  language: 'en',
  sortBy: 'relevancy',
  pageSize: 10,
  page: 1,
};
const relative = raw.match(/(last|past|previous)\\s+(\\d{1,3})\\s+(hours?|days?|weeks?|months?)/i);
if (relative) {
  const amount = Math.min(Number(relative[2]), 365);
  const unit = relative[3].toLowerCase();
  const hours = unit.startsWith('hour') ? amount : unit.startsWith('week') ? amount * 168 : unit.startsWith('month') ? amount * 720 : amount * 24;
  params.from = new Date(Date.now() - hours * 3600000).toISOString();
}
return [{ json: { kind: 'news_search_plan', raw_input: raw, topic, endpoint: '/everything', params } }];"""
    return {
        "id": _node_id(),
        "name": node.name,
        "type": _N8N_CODE_TYPE,
        "typeVersion": 2,
        "position": [round(x), round(y)],
        "parameters": {"jsCode": code},
    }


def _manual_trigger_node(x: float, y: float) -> dict[str, Any]:
    return {
        "id": _node_id(),
        "name": "When clicking \u2019Test workflow\u2019",
        "type": _N8N_MANUAL_TRIGGER_TYPE,
        "typeVersion": 1,
        "position": [round(x), round(y)],
        "parameters": {},
    }


def _set_input_node(x: float, y: float) -> dict[str, Any]:
    """A Set node to inject an initial 'input' field."""
    return {
        "id": _node_id(),
        "name": "Set Input",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [round(x), round(y)],
        "parameters": {
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {
                        "id": _node_id(),
                        "name": "input",
                        "value": "={{ $json.input ?? 'Start the workflow.' }}",
                        "type": "string",
                    }
                ]
            },
        },
    }


def _switch_node(node: WorkflowNode, labels: list[str], x: float, y: float) -> dict[str, Any]:
    values = []
    for index, label in enumerate(labels):
        route = label or f"path_{index + 1}"
        values.append({
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "leftValue": "={{ $json.output ?? $json.route ?? '' }}",
                    "rightValue": route,
                    "operator": {"type": "string", "operation": "contains"},
                }],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": route,
        })
    return {
        "id": _node_id(),
        "name": f"Route ({node.name})",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [round(x + 220), round(y)],
        "parameters": {"rules": {"values": values}, "options": {}},
    }


def _execution_layout(
    workflow: Workflow,
    execution_nodes: list[WorkflowNode],
    trigger_ids: set[str],
) -> tuple[dict[str, tuple[float, float]], float]:
    """Lay out the executable DAG by stage, stacking parallel nodes vertically."""
    visible = [node for node in execution_nodes if node.id not in trigger_ids]
    visible_ids = {node.id for node in visible}
    incoming: dict[str, set[str]] = {node.id: set() for node in visible}
    outgoing: dict[str, set[str]] = {node.id: set() for node in visible}
    for edge in workflow.edges:
        if edge.kind not in {"flow", "conditional"}:
            continue
        if edge.source in visible_ids and edge.target in visible_ids:
            incoming[edge.target].add(edge.source)
            outgoing[edge.source].add(edge.target)

    levels = {node.id: 0 for node in visible}
    indegree = {node_id: len(sources) for node_id, sources in incoming.items()}
    queue = [node.id for node in visible if indegree[node.id] == 0]
    while queue:
        source = queue.pop(0)
        for target in outgoing[source]:
            levels[target] = max(levels[target], levels[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    stages: dict[int, list[str]] = {}
    for node in visible:
        stages.setdefault(levels[node.id], []).append(node.id)
    max_parallel = max((len(node_ids) for node_ids in stages.values()), default=1)
    canvas_center_y = _GRID_Y_START + ((max_parallel - 1) * _GRID_Y_STEP / 2)
    positions: dict[str, tuple[float, float]] = {}
    first_agent_x = _GRID_X_START + (2 * _GRID_X_STEP)
    for level, node_ids in stages.items():
        stage_top = canvas_center_y - ((len(node_ids) - 1) * _GRID_Y_STEP / 2)
        for row, node_id in enumerate(node_ids):
            positions[node_id] = (
                first_agent_x + (level * _GRID_X_STEP),
                stage_top + (row * _GRID_Y_STEP),
            )
    return positions, canvas_center_y


def workflow_to_n8n(workflow: Workflow) -> dict[str, Any]:
    """Convert a Nodara workflow to an n8n-compatible JSON object.

    Layout strategy:
    - Columns represent dependency stages.
    - Nodes in the same stage are stacked as parallel branches.
    - Fan-in nodes return to the vertical center of the canvas.
    - Each agent has its own OpenAI Chat Model node below it.
    """
    nodes: list[dict[str, Any]] = []
    connections: dict[str, Any] = {}

    execution_nodes = [node for node in workflow.nodes if node.type not in _SUPPORT_TYPES]
    trigger_ids = {node.id for node in execution_nodes if node.type == "trigger"}
    positions, canvas_center_y = _execution_layout(workflow, execution_nodes, trigger_ids)

    x = _GRID_X_START
    y = canvas_center_y

    # ── Trigger ──────────────────────────────────────────────────────────────
    trigger = _manual_trigger_node(x, y)
    nodes.append(trigger)
    x += _GRID_X_STEP

    # ── Set Input ─────────────────────────────────────────────────────────────
    set_input = _set_input_node(x, y)
    nodes.append(set_input)

    # Trigger → Set Input
    connections[trigger["name"]] = {
        "main": [[{"node": set_input["name"], "type": "main", "index": 0}]]
    }
    x += _GRID_X_STEP

    # ── Agent nodes ───────────────────────────────────────────────────────────
    # Build a name→node_id lookup for edges
    name_to_n8n: dict[str, str] = {}   # workflow_node.id → n8n node name
    edge_source_name: dict[str, str] = {}
    conditional_output_index: dict[tuple[str, str, str], int] = {}
    agent_nodes: list[tuple[str, str]] = []
    # A drawn trigger maps to the real n8n trigger + input pair rather than a
    # redundant AI Agent node.
    for trigger_id in trigger_ids:
        name_to_n8n[trigger_id] = set_input["name"]

    for wf_node in execution_nodes:
        if wf_node.id in trigger_ids:
            continue
        node_x, node_y = positions[wf_node.id]
        if wf_node.type == "query_builder":
            exported_node = _query_builder_n8n_node(wf_node, node_x, node_y)
            nodes.append(exported_node)
        elif rss_source_id(wf_node):
            exported_node = _newsapi_http_node(wf_node, node_x, node_y)
            nodes.append(exported_node)
        else:
            exported_node = _agent_n8n_node(wf_node, node_x, node_y)
            model = _openai_model_node(wf_node.name, wf_node.model, node_x, node_y)
            nodes.append(exported_node)
            nodes.append(model)

            # Agent ← Chat Model (ai_languageModel port)
            connections[model["name"]] = {
                "ai_languageModel": [[{"node": exported_node["name"], "type": "ai_languageModel", "index": 0}]]
            }

        name_to_n8n[wf_node.id] = exported_node["name"]
        edge_source_name[wf_node.id] = exported_node["name"]
        agent_nodes.append((wf_node.id, exported_node["name"]))
        if wf_node.type == "condition":
            outgoing = [edge for edge in workflow.edges if edge.source == wf_node.id and edge.kind in {"flow", "conditional"}]
            labels = [edge.label for edge in outgoing]
            switch = _switch_node(wf_node, labels, node_x, node_y)
            nodes.append(switch)
            edge_source_name[wf_node.id] = switch["name"]
            connections[exported_node["name"]] = {"main": [[{"node": switch["name"], "type": "main", "index": 0}]]}
            for output_index, edge in enumerate(outgoing):
                conditional_output_index[(edge.source, edge.target, edge.label)] = output_index

    def add_main_connection(source_name: str, target_name: str, output_index: int = 0) -> None:
        outputs = connections.setdefault(source_name, {}).setdefault("main", [])
        while len(outputs) <= output_index:
            outputs.append([])
        bucket = outputs[output_index]
        connection = {"node": target_name, "type": "main", "index": 0}
        if connection not in bucket:
            bucket.append(connection)

    # ── Wire edges (agent → agent) ────────────────────────────────────────────
    for edge in workflow.edges:
        src_name = edge_source_name.get(edge.source) or name_to_n8n.get(edge.source)
        tgt_name = name_to_n8n.get(edge.target)
        if src_name and tgt_name:
            output_index = conditional_output_index.get((edge.source, edge.target, edge.label), 0)
            add_main_connection(src_name, tgt_name, output_index)

    # If the drawing has no explicit trigger, connect Set Input to every
    # zero-indegree execution root so parallel starts remain parallel.
    if not trigger_ids:
        incoming = {node_id: 0 for node_id, _ in agent_nodes}
        for edge in workflow.edges:
            if edge.kind in {"flow", "conditional"} and edge.target in incoming and edge.source in name_to_n8n:
                incoming[edge.target] += 1
        for node_id, node_name in agent_nodes:
            if incoming[node_id] == 0:
                add_main_connection(set_input["name"], node_name)

    # If no explicit edges, auto-wire agents sequentially
    if not workflow.edges and len(agent_nodes) > 1:
        for i in range(len(agent_nodes) - 1):
            src_name = agent_nodes[i][1]
            tgt_name = agent_nodes[i + 1][1]
            add_main_connection(src_name, tgt_name)

    return {
        "name": workflow.name,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": "",
        },
        "versionId": str(uuid.uuid4()),
        "meta": {
            "templateCredsSetupCompleted": True,
            "instanceId": "mobile-agent-builder",
        },
        "id": workflow.id,
        "tags": ["mobile-agent-builder"],
    }
