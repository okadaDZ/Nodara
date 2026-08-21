import { Workflow, WorkflowEdge, WorkflowNode } from '@/types/workflow';

const SUPPORT_TYPES = new Set(['tool', 'memory', 'parser']);
const EXECUTION_EDGE_KINDS = new Set(['flow', 'conditional']);

const isExecutionEdge = (edge: WorkflowEdge) => EXECUTION_EDGE_KINDS.has(edge.kind ?? 'flow');
const edgeKey = (edge: WorkflowEdge) => `${edge.source}|${edge.target}|${edge.kind ?? 'flow'}|${edge.label ?? ''}`;

export function normalizeWorkflow(workflow: Workflow): Workflow {
  const nodeIds = new Set(workflow.nodes.map((node) => node.id));
  const seen = new Set<string>();
  const edges = workflow.edges.filter((edge) => {
    const key = edgeKey(edge);
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target) || edge.source === edge.target || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
  return { ...workflow, edges };
}

export function wouldCreateCycle(workflow: Workflow, source: string, target: string): boolean {
  if (source === target) return true;
  const outgoing = new Map<string, string[]>();
  workflow.edges.filter(isExecutionEdge).forEach((edge) => {
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge.target]);
  });
  const queue = [target];
  const visited = new Set<string>();
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === source) return true;
    if (visited.has(current)) continue;
    visited.add(current);
    queue.push(...(outgoing.get(current) ?? []));
  }
  return false;
}

export function removeNodePreservingFlow(workflow: Workflow, nodeId: string): Workflow {
  const node = workflow.nodes.find((candidate) => candidate.id === nodeId);
  if (!node) return workflow;

  const removedIds = new Set([nodeId]);
  if (!SUPPORT_TYPES.has(node.type)) {
    workflow.edges.forEach((edge) => {
      if (!['tool', 'memory', 'parser'].includes(edge.kind ?? 'flow')) return;
      if (edge.source === nodeId) removedIds.add(edge.target);
      if (edge.target === nodeId) removedIds.add(edge.source);
    });
  }

  const predecessors = workflow.edges.filter(
    (edge) => edge.target === nodeId && isExecutionEdge(edge) && !removedIds.has(edge.source),
  );
  const successors = workflow.edges.filter(
    (edge) => edge.source === nodeId && isExecutionEdge(edge) && !removedIds.has(edge.target),
  );
  const retainedEdges = workflow.edges.filter(
    (edge) => !removedIds.has(edge.source) && !removedIds.has(edge.target),
  );
  const existing = new Set(retainedEdges.map(edgeKey));
  const bridges: WorkflowEdge[] = [];
  predecessors.forEach((incoming) => {
    successors.forEach((outgoing, index) => {
      const branchEdge = outgoing.kind === 'conditional' ? outgoing : incoming;
      const bridge: WorkflowEdge = {
        id: `edge_bridge_${Date.now().toString(36)}_${index}_${incoming.source}_${outgoing.target}`,
        source: incoming.source,
        target: outgoing.target,
        kind: branchEdge.kind ?? 'flow',
        label: branchEdge.label,
      };
      if (!existing.has(edgeKey(bridge)) && !wouldCreateCycle({ ...workflow, edges: [...retainedEdges, ...bridges] }, bridge.source, bridge.target)) {
        existing.add(edgeKey(bridge));
        bridges.push(bridge);
      }
    });
  });

  return normalizeWorkflow({
    ...workflow,
    nodes: workflow.nodes.filter((candidate) => !removedIds.has(candidate.id)),
    edges: [...retainedEdges, ...bridges],
  });
}

export function insertNode(
  workflow: Workflow,
  node: WorkflowNode,
  predecessorIds: string[],
  successorIds: string[],
): Workflow {
  if (SUPPORT_TYPES.has(node.type)) {
    const anchor = predecessorIds[0];
    if (!anchor) return { ...workflow, nodes: [...workflow.nodes, node] };
    return normalizeWorkflow({
      ...workflow,
      nodes: [...workflow.nodes, node],
      edges: [
        ...workflow.edges,
        { id: `edge_${node.id}_${anchor}`, source: node.id, target: anchor, kind: node.type as 'tool' | 'memory' | 'parser', label: node.type },
      ],
    });
  }

  const predecessorSet = new Set(predecessorIds);
  const successorSet = new Set(successorIds);
  const replacedEdges = workflow.edges.filter(
    (edge) => isExecutionEdge(edge) && predecessorSet.has(edge.source) && successorSet.has(edge.target),
  );
  const retainedEdges = workflow.edges.filter(
    (edge) => !(isExecutionEdge(edge) && predecessorSet.has(edge.source) && successorSet.has(edge.target)),
  );
  const candidates: WorkflowEdge[] = [
    ...predecessorIds.map((source, index) => {
      const sourceEdges = replacedEdges.filter((edge) => edge.source === source);
      const signature = new Set(sourceEdges.map((edge) => `${edge.kind ?? 'flow'}|${edge.label ?? ''}`));
      const inherited = signature.size === 1 ? sourceEdges[0] : undefined;
      return {
        id: `edge_${source}_${node.id}_${index}`,
        source,
        target: node.id,
        kind: inherited?.kind ?? 'flow' as const,
        label: inherited?.label,
      };
    }),
    ...successorIds.map((target, index) => ({
      id: `edge_${node.id}_${target}_${index}`,
      source: node.id,
      target,
      kind: 'flow' as const,
    })),
  ];
  const graphWithNode = { ...workflow, nodes: [...workflow.nodes, node] };
  const addedEdges: WorkflowEdge[] = [];
  candidates.forEach((edge) => {
    const current = { ...graphWithNode, edges: [...retainedEdges, ...addedEdges] };
    if (!wouldCreateCycle(current, edge.source, edge.target)) addedEdges.push(edge);
  });
  return normalizeWorkflow({
    ...graphWithNode,
    edges: [...retainedEdges, ...addedEdges],
  });
}

export function attachSupportNode(workflow: Workflow, nodeId: string, anchorId?: string): Workflow {
  const node = workflow.nodes.find((candidate) => candidate.id === nodeId);
  if (!node || !SUPPORT_TYPES.has(node.type)) return workflow;
  const retainedEdges = workflow.edges.filter(
    (edge) => !(edge.source === nodeId && ['tool', 'memory', 'parser'].includes(edge.kind ?? 'flow')),
  );
  if (!anchorId) return normalizeWorkflow({ ...workflow, edges: retainedEdges });
  return normalizeWorkflow({
    ...workflow,
    edges: [
      ...retainedEdges,
      { id: `edge_${nodeId}_${anchorId}`, source: nodeId, target: anchorId, kind: node.type as 'tool' | 'memory' | 'parser', label: node.type },
    ],
  });
}

export function rewireIncomingEdges(workflow: Workflow, nodeId: string, predecessorIds: string[]): Workflow {
  const retainedEdges = workflow.edges.filter((edge) => !(edge.target === nodeId && isExecutionEdge(edge)));
  const base = { ...workflow, edges: retainedEdges };
  const safePredecessors = predecessorIds.filter((source) => !wouldCreateCycle(base, source, nodeId));
  return normalizeWorkflow({
    ...workflow,
    edges: [
      ...retainedEdges,
      ...safePredecessors.map((source, index) => ({
        id: `edge_${source}_${nodeId}_${Date.now().toString(36)}_${index}`,
        source,
        target: nodeId,
        kind: 'flow' as const,
      })),
    ],
  });
}

export function executionNodeCount(workflow: Workflow): number {
  return workflow.nodes.filter((node) => !SUPPORT_TYPES.has(node.type)).length;
}
