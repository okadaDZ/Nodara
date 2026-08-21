from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from libs.database.repositories import RunRepository
from libs.langgraph.compiler import CompiledWorkflowGraph, WorkflowCompilationError, WorkflowGraphCompiler
from libs.langgraph.state import WorkflowGraphState
from libs.models.run import WorkflowRun
from libs.models.workflow import Workflow, WorkflowNode
from libs.runtime.agent_executor import AgentExecutionResult, AgentExecutor
from libs.runtime.rss_source import RssTriggerExecutor
from libs.langchain.langfuse_client import langchain_config, trace_scope

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RuntimeLimits:
    max_steps: int = 100
    timeout_seconds: float = 300.0


class LangGraphWorkflowExecutor:
    """Compile and execute a saved Nodara workflow through LangGraph."""

    def __init__(
        self,
        agent_executor: AgentExecutor | None = None,
        compiler: WorkflowGraphCompiler | None = None,
        limits: RuntimeLimits | None = None,
        rss_trigger_executor: RssTriggerExecutor | None = None,
    ):
        self.agent_executor = agent_executor or AgentExecutor()
        self.compiler = compiler or WorkflowGraphCompiler()
        self.limits = limits or RuntimeLimits()
        self.rss_trigger_executor = rss_trigger_executor or RssTriggerExecutor()

    @staticmethod
    def _predecessor_input(
        predecessor_ids: list[str],
        nodes_by_id: dict[str, WorkflowNode],
        outputs: dict[str, str],
    ) -> str | None:
        available = [(node_id, outputs[node_id]) for node_id in predecessor_ids if node_id in outputs]
        if not available:
            return None
        if len(available) == 1:
            return available[0][1]
        return "Outputs from parallel preceding agents:\n\n" + "\n\n".join(
            f"[{nodes_by_id[node_id].name}]\n{output}" for node_id, output in available
        )

    async def _select_route(
        self,
        node: WorkflowNode,
        original_input: str,
        predecessor_output: str | None,
        route_map: dict[str, str],
    ) -> AgentExecutionResult:
        labels = list(route_map)
        prompt = (
            f"Initial workflow request:\n{original_input}\n\n"
            f"Previous output:\n{predecessor_output or '(none)'}\n\n"
            f"Choose exactly one route from: {', '.join(labels)}.\n"
            "Return only the route label, with no explanation."
        )
        try:
            output = await self.agent_executor.provider.generate_text(
                prompt=prompt,
                system_prompt=node.instructions or node.description or "Select the correct workflow route.",
                model_name=node.model,
            )
            selected = output.strip().strip('"').strip("'")
            exact = next((label for label in labels if selected.casefold() == label.casefold()), None)
            if not exact:
                return AgentExecutionResult(
                    success=False,
                    output="",
                    error=f"Router '{node.name}' returned '{selected}', expected one of: {', '.join(labels)}.",
                )
            return AgentExecutionResult(success=True, output=exact)
        except Exception as exc:
            return AgentExecutionResult(success=False, output="", error=str(exc))

    def compile(self, workflow: Workflow, run_id: str, run_repo: RunRepository) -> CompiledWorkflowGraph:
        nodes_by_id = {node.id: node for node in workflow.nodes}

        def node_factory(node: WorkflowNode, predecessor_ids: list[str], route_map: dict[str, str]):
            async def execute(state: WorkflowGraphState) -> dict:
                original_input = state["original_input"]
                previous_output = self._predecessor_input(
                    predecessor_ids, nodes_by_id, state.get("outputs", {})
                )
                input_data = previous_output or original_input
                run_repo.update_node_status(
                    run_id=run_id,
                    node_id=node.id,
                    status="running",
                    input_data=input_data,
                    started_at=utc_now(),
                )

                if node.type == "query_builder":
                    result = AgentExecutionResult(
                        success=True,
                        output=self.rss_trigger_executor.plan_query(input_data),
                    )
                elif self.rss_trigger_executor.supports(node, is_root=not predecessor_ids):
                    source_provider = self.rss_trigger_executor.provider_name
                    with trace_scope(
                        f"news.fetch-{source_provider}",
                        input={"node_id": node.id, "node_name": node.name},
                        tags=["news", "rss", f"{source_provider}-source"],
                        metadata={
                            "workflow_id": workflow.id,
                            "run_id": run_id,
                            "provider": source_provider,
                        },
                        as_type="tool",
                    ) as rss_trace:
                        rss_output = await self.rss_trigger_executor.execute(node, input_data)
                        rss_trace.update(output={"payload": rss_output})
                    result = AgentExecutionResult(success=True, output=rss_output)
                elif node.type in {"input", "trigger"}:
                    result = AgentExecutionResult(success=True, output=original_input)
                elif node.type in {"condition", "router"}:
                    result = await self._select_route(
                        node, original_input, previous_output, route_map
                    )
                elif node.type == "output" and not node.instructions.strip():
                    result = AgentExecutionResult(success=True, output=input_data)
                else:
                    result = await self.agent_executor.execute(
                        node=node,
                        original_input=original_input,
                        previous_output=previous_output,
                    )

                if not result.success:
                    error = result.error or f"Node '{node.name}' failed."
                    run_repo.update_node_status(
                        run_id=run_id,
                        node_id=node.id,
                        status="failed",
                        error=error,
                        finished_at=utc_now(),
                    )
                    raise RuntimeError(error)

                run_repo.update_node_status(
                    run_id=run_id,
                    node_id=node.id,
                    status="completed",
                    output_data=result.output,
                    finished_at=utc_now(),
                )
                update: dict = {"outputs": {node.id: result.output}, "steps": 1}
                if route_map:
                    update["routes"] = {node.id: result.output}
                return update

            return execute

        return self.compiler.compile(workflow, node_factory)

    async def run(
        self,
        workflow: Workflow,
        run_id: str,
        input_text: str,
        run_repo: RunRepository,
    ) -> WorkflowRun:
        try:
            compiled = self.compile(workflow, run_id, run_repo)
            initial_state: WorkflowGraphState = {
                "original_input": input_text,
                "outputs": {},
                "routes": {},
                "errors": [],
                "steps": 0,
            }
            trace_metadata = {
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "run_id": run_id,
                "node_count": len(workflow.nodes),
                "edge_count": len(workflow.edges),
            }
            with trace_scope(
                "workflow.execute",
                input={"request": input_text},
                session_id=workflow.id,
                tags=["langgraph", "workflow-execution"],
                metadata=trace_metadata,
                as_type="agent",
            ) as trace:
                result = await asyncio.wait_for(
                    compiled.graph.ainvoke(
                        initial_state,
                        config=langchain_config(
                            "workflow.graph",
                            metadata=trace_metadata,
                            recursion_limit=self.limits.max_steps,
                        ),
                    ),
                    timeout=self.limits.timeout_seconds,
                )
                trace.update(output={"outputs": result.get("outputs", {})})
            outputs = result.get("outputs", {})
            final_parts = [outputs[node_id] for node_id in compiled.sinks if node_id in outputs]
            final_output = final_parts[0] if len(final_parts) == 1 else "\n\n".join(final_parts)
            current_run = run_repo.get_run(run_id)
            if current_run:
                for node_run in current_run.nodes:
                    if node_run.status == "waiting":
                        run_repo.update_node_status(
                            run_id=run_id,
                            node_id=node_run.node_id,
                            status="skipped",
                            finished_at=utc_now(),
                        )
            run_repo.finish_run(run_id, status="completed", final_output=final_output)
        except asyncio.TimeoutError:
            run_repo.finish_run(
                run_id, status="failed", error=f"Workflow exceeded {self.limits.timeout_seconds:g} seconds."
            )
        except Exception as exc:
            logger.error("LangGraph workflow run %s failed: %s", run_id, exc, exc_info=True)
            run_repo.finish_run(run_id, status="failed", error=str(exc))

        return run_repo.get_run(run_id) or WorkflowRun(
            id=run_id,
            workflow_id=workflow.id,
            status="failed",
            input=input_text,
            error="Run record unavailable.",
        )
