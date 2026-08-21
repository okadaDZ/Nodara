# Nodara LangGraph runtime

This package is the execution boundary between a saved visual workflow and LangGraph.

## Runtime path

1. `WorkflowGraphCompiler.validate()` rejects unsupported or ambiguous graphs.
2. `WorkflowGraphCompiler.compile()` maps the saved workflow IR to a `StateGraph`.
3. `LangGraphWorkflowExecutor` executes nodes and persists each status transition.
4. Parallel branches update a reducer-backed output map.
5. Multi-source edges become explicit fan-in barriers, so a join runs once after all inputs.
6. A `condition` or `router` node chooses exactly one labeled conditional edge.
7. Nodes not activated by the chosen route are persisted as `skipped`.

## Supported executable nodes

- `input` / `trigger`: publishes the original run input without an LLM call.
- `agent`: executes its generated system prompt with its assigned model.
- `output`: passes through merged input, or uses an LLM when instructions are present.
- `condition` / `router`: returns exactly one outgoing edge label.

Tool, memory, and parser nodes remain graph metadata until they are connected to a gated runtime registry. Unknown executable node types fail compilation. Cycles remain rejected by the canonical workflow model; bounded loop execution and human checkpoints are deliberately separate milestones.

## Safety limits

The executor applies a LangGraph recursion limit and a wall-clock timeout. Provider failures fail the run and persist the failing node. The compiler never asks an LLM to repair topology at run time.
