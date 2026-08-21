from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from libs.database.repositories import RunRepository
from libs.models.workflow import Workflow, WorkflowNode
from libs.models.run import WorkflowRun
from libs.runtime.agent_executor import AgentExecutor, AgentExecutionResult

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SequentialWorkflowExecutor:
    """Execute a workflow DAG in dependency waves.

    The historical class name is retained for compatibility. Independent nodes
    in each wave run concurrently; merge nodes receive every predecessor output.
    """

    def __init__(self, agent_executor: AgentExecutor | None = None):
        self.agent_executor = agent_executor or AgentExecutor()

    @staticmethod
    def _predecessor_input(
        node: WorkflowNode,
        predecessor_ids: list[str],
        nodes_by_id: dict[str, WorkflowNode],
        outputs: dict[str, str],
    ) -> str | None:
        available = [(node_id, outputs[node_id]) for node_id in predecessor_ids if node_id in outputs]
        if not available:
            return None
        if len(available) == 1:
            return available[0][1]
        sections = [
            f"[{nodes_by_id[node_id].name}]\n{output}"
            for node_id, output in available
        ]
        return "Outputs from parallel preceding agents:\n\n" + "\n\n".join(sections)

    async def run(
        self,
        workflow: Workflow,
        run_id: str,
        input_text: str,
        run_repo: RunRepository,
    ) -> WorkflowRun:
        logger.info("Starting DAG execution for run %s on workflow %s", run_id, workflow.id)

        support_types = {"tool", "memory", "parser"}
        execution_nodes = [node for node in workflow.nodes if node.type not in support_types]
        nodes_by_id = {node.id: node for node in execution_nodes}
        predecessors: dict[str, list[str]] = {node.id: [] for node in execution_nodes}
        outgoing: dict[str, list[str]] = {node.id: [] for node in execution_nodes}
        for edge in workflow.edges:
            if edge.kind in {"flow", "conditional"} and edge.source in nodes_by_id and edge.target in nodes_by_id and edge.source != edge.target:
                predecessors[edge.target].append(edge.source)
                outgoing[edge.source].append(edge.target)

        pending = set(nodes_by_id)
        outputs: dict[str, str] = {}

        while pending:
            ready_ids = [
                node.id
                for node in execution_nodes
                if node.id in pending and all(source_id not in pending for source_id in predecessors[node.id])
            ]
            if not ready_ids:
                error = "Workflow contains a dependency cycle and cannot be executed."
                run_repo.finish_run(run_id=run_id, status="failed", error=error)
                return run_repo.get_run(run_id) or WorkflowRun(
                    id=run_id,
                    workflow_id=workflow.id,
                    status="failed",
                    input=input_text,
                    error=error,
                )

            tasks = []
            for node_id in ready_ids:
                node = nodes_by_id[node_id]
                previous_output = self._predecessor_input(
                    node, predecessors[node_id], nodes_by_id, outputs
                )
                run_repo.update_node_status(
                    run_id=run_id,
                    node_id=node_id,
                    status="running",
                    input_data=previous_output or input_text,
                    started_at=utc_now(),
                )
                tasks.append(
                    self.agent_executor.execute(
                        node=node,
                        original_input=input_text,
                        previous_output=previous_output,
                    )
                )

            results: list[AgentExecutionResult] = await asyncio.gather(*tasks)
            failed = False
            first_error: str | None = None
            for node_id, result in zip(ready_ids, results):
                if result.success:
                    outputs[node_id] = result.output
                    run_repo.update_node_status(
                        run_id=run_id,
                        node_id=node_id,
                        status="completed",
                        output_data=result.output,
                        finished_at=utc_now(),
                    )
                else:
                    failed = True
                    first_error = first_error or result.error or "Agent execution failed."
                    run_repo.update_node_status(
                        run_id=run_id,
                        node_id=node_id,
                        status="failed",
                        error=result.error,
                        finished_at=utc_now(),
                    )
                pending.remove(node_id)

            if failed:
                run_repo.finish_run(run_id=run_id, status="failed", error=first_error)
                return run_repo.get_run(run_id) or WorkflowRun(
                    id=run_id,
                    workflow_id=workflow.id,
                    status="failed",
                    input=input_text,
                    error=first_error,
                )

        sink_ids = [node.id for node in execution_nodes if not outgoing[node.id]]
        final_sections = [outputs[node_id] for node_id in sink_ids if node_id in outputs]
        final_output = (
            final_sections[0]
            if len(final_sections) == 1
            else "\n\n".join(final_sections)
        )
        run_repo.finish_run(run_id=run_id, status="completed", final_output=final_output)
        return run_repo.get_run(run_id) or WorkflowRun(
            id=run_id,
            workflow_id=workflow.id,
            status="completed",
            input=input_text,
            final_output=final_output,
        )
