from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from libs.langgraph.state import WorkflowGraphState
from libs.models.workflow import SUPPORT_TYPES, Workflow, WorkflowNode

ExecutableNode = Callable[[WorkflowGraphState], Awaitable[dict]]
NodeFactory = Callable[[WorkflowNode, list[str], dict[str, str]], ExecutableNode]


class WorkflowCompilationError(ValueError):
    """The saved visual workflow cannot be compiled into a safe runtime graph."""


@dataclass(frozen=True)
class CompiledWorkflowGraph:
    graph: CompiledStateGraph
    roots: tuple[str, ...]
    sinks: tuple[str, ...]


class WorkflowGraphCompiler:
    """Compile the Nodara workflow IR into a LangGraph state machine.

    The compiler is deterministic. It never asks an LLM to repair malformed
    topology during execution.
    """

    EXECUTABLE_TYPES = {"agent", "input", "trigger", "query_builder", "output", "condition", "router"}

    def validate(self, workflow: Workflow) -> None:
        execution_nodes = [node for node in workflow.nodes if node.type not in SUPPORT_TYPES]
        if not execution_nodes:
            raise WorkflowCompilationError("Workflow has no executable nodes.")

        unsupported = sorted({node.type for node in execution_nodes} - self.EXECUTABLE_TYPES)
        if unsupported:
            raise WorkflowCompilationError(
                "Unsupported executable node type(s): " + ", ".join(unsupported)
            )

        node_by_id = {node.id: node for node in execution_nodes}
        outgoing = {node.id: [] for node in execution_nodes}
        for edge in workflow.edges:
            if edge.source not in node_by_id or edge.target not in node_by_id:
                continue
            outgoing[edge.source].append(edge)

        for node_id, edges in outgoing.items():
            conditional = [edge for edge in edges if edge.kind == "conditional"]
            normal = [edge for edge in edges if edge.kind == "flow"]
            node = node_by_id[node_id]
            if conditional and node.type not in {"condition", "router"}:
                raise WorkflowCompilationError(
                    f"Node '{node.name}' has conditional edges but is not a condition/router node."
                )
            if node.type in {"condition", "router"}:
                if normal or len(conditional) < 2:
                    raise WorkflowCompilationError(
                        f"Router '{node.name}' needs at least two labeled conditional edges and no flow edges."
                    )
                labels = [edge.label.strip() for edge in conditional]
                if any(not label for label in labels) or len(labels) != len(set(labels)):
                    raise WorkflowCompilationError(
                        f"Router '{node.name}' needs a unique non-empty label on every outgoing edge."
                    )

    def compile(self, workflow: Workflow, node_factory: NodeFactory) -> CompiledWorkflowGraph:
        self.validate(workflow)
        nodes = [node for node in workflow.nodes if node.type not in SUPPORT_TYPES]
        node_by_id = {node.id: node for node in nodes}
        predecessors: dict[str, list[str]] = {node.id: [] for node in nodes}
        flow_outgoing: dict[str, list[str]] = {node.id: [] for node in nodes}
        route_maps: dict[str, dict[str, str]] = {}

        for edge in workflow.edges:
            if edge.source not in node_by_id or edge.target not in node_by_id:
                continue
            predecessors[edge.target].append(edge.source)
            if edge.kind == "conditional":
                route_maps.setdefault(edge.source, {})[edge.label.strip()] = edge.target
            elif edge.kind == "flow":
                flow_outgoing[edge.source].append(edge.target)

        builder = StateGraph(WorkflowGraphState)
        for node in nodes:
            builder.add_node(
                node.id,
                node_factory(node, predecessors[node.id], route_maps.get(node.id, {})),
            )

        roots = tuple(node.id for node in nodes if not predecessors[node.id])
        if not roots:
            raise WorkflowCompilationError("Workflow has no starting node.")
        for root in roots:
            builder.add_edge(START, root)

        flow_predecessors: dict[str, list[str]] = {node.id: [] for node in nodes}
        for source_id, targets in flow_outgoing.items():
            for target_id in targets:
                flow_predecessors[target_id].append(source_id)
        for target_id, source_ids in flow_predecessors.items():
            if len(source_ids) == 1:
                builder.add_edge(source_ids[0], target_id)
            elif source_ids:
                # A list edge is LangGraph's explicit fan-in barrier: the join
                # executes once, only after every parallel predecessor finishes.
                builder.add_edge(source_ids, target_id)

        for router_id, route_map in route_maps.items():
            def select_route(state: WorkflowGraphState, current_id: str = router_id) -> str:
                selected = state.get("routes", {}).get(current_id)
                if not selected:
                    raise WorkflowCompilationError(f"Router '{current_id}' produced no route.")
                return selected

            builder.add_conditional_edges(router_id, select_route, route_map)

        outgoing_targets = {
            source
            for source, targets in flow_outgoing.items()
            if targets or source in route_maps
        }
        sinks = tuple(node.id for node in nodes if node.id not in outgoing_targets)
        for sink in sinks:
            builder.add_edge(sink, END)

        return CompiledWorkflowGraph(graph=builder.compile(), roots=roots, sinks=sinks)
