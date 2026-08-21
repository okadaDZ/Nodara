import { Workflow, WorkflowEdge, WorkflowNode } from '@/types/workflow';

export const NODE_WIDTH = 184;
export const NODE_HEIGHT = 108;
export const COLUMN_GAP = 86;
export const ROW_GAP = 34;
export const CANVAS_PADDING = 28;

const SUPPORT_TYPES = new Set(['tool', 'memory', 'parser']);

export interface PositionedWorkflowNode extends WorkflowNode {
  layoutX: number;
  layoutY: number;
  stage: number;
  isSupport: boolean;
}

export interface WorkflowCanvasLayout {
  nodes: PositionedWorkflowNode[];
  edges: WorkflowEdge[];
  width: number;
  height: number;
  stageCount: number;
  maxParallel: number;
  supportCount: number;
  hasCycle: boolean;
}

/** Layout execution nodes as a DAG and place tool/memory/parser attachments below their owner. */
export function layoutWorkflow(workflow: Workflow): WorkflowCanvasLayout {
  const nodeIds = new Set(workflow.nodes.map((node) => node.id));
  const edges = workflow.edges.filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target) && edge.source !== edge.target,
  );
  const mainNodes = workflow.nodes.filter((node) => !SUPPORT_TYPES.has(node.type));
  const supportNodes = workflow.nodes.filter((node) => SUPPORT_TYPES.has(node.type));
  const mainIds = new Set(mainNodes.map((node) => node.id));
  const flowEdges = edges.filter(
    (edge) =>
      (edge.kind ?? 'flow') !== 'tool' &&
      (edge.kind ?? 'flow') !== 'memory' &&
      (edge.kind ?? 'flow') !== 'parser' &&
      mainIds.has(edge.source) &&
      mainIds.has(edge.target),
  );

  const incoming = new Map(mainNodes.map((node) => [node.id, 0]));
  const outgoing = new Map(mainNodes.map((node) => [node.id, [] as string[]]));
  const stage = new Map(mainNodes.map((node) => [node.id, 0]));
  flowEdges.forEach((edge) => {
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
    outgoing.get(edge.source)?.push(edge.target);
  });

  const queue = mainNodes.filter((node) => incoming.get(node.id) === 0).map((node) => node.id);
  const visited = new Set<string>();
  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    visited.add(nodeId);
    const sourceStage = stage.get(nodeId) ?? 0;
    for (const targetId of outgoing.get(nodeId) ?? []) {
      stage.set(targetId, Math.max(stage.get(targetId) ?? 0, sourceStage + 1));
      const remaining = (incoming.get(targetId) ?? 1) - 1;
      incoming.set(targetId, remaining);
      if (remaining === 0) queue.push(targetId);
    }
  }

  const hasCycle = visited.size !== mainNodes.length;
  const lastStage = Math.max(0, ...Array.from(stage.values()));
  mainNodes.forEach((node) => {
    if (!visited.has(node.id)) stage.set(node.id, lastStage + 1);
  });

  const stages = new Map<number, WorkflowNode[]>();
  mainNodes.forEach((node) => {
    const nodeStage = stage.get(node.id) ?? 0;
    stages.set(nodeStage, [...(stages.get(nodeStage) ?? []), node]);
  });
  const stageCount = Math.max(1, ...Array.from(stages.keys()).map((value) => value + 1));
  const maxParallel = Math.max(1, ...Array.from(stages.values()).map((items) => items.length));
  const mainHeight = Math.max(
    340,
    CANVAS_PADDING * 2 + maxParallel * NODE_HEIGHT + Math.max(0, maxParallel - 1) * ROW_GAP,
  );
  const width = Math.max(
    340,
    CANVAS_PADDING * 2 + stageCount * NODE_WIDTH + Math.max(0, stageCount - 1) * COLUMN_GAP,
  );

  const positionedMain: PositionedWorkflowNode[] = mainNodes.map((node) => {
    const nodeStage = stage.get(node.id) ?? 0;
    const stageNodes = stages.get(nodeStage) ?? [node];
    const row = stageNodes.findIndex((candidate) => candidate.id === node.id);
    const groupHeight = stageNodes.length * NODE_HEIGHT + Math.max(0, stageNodes.length - 1) * ROW_GAP;
    return {
      ...node,
      stage: nodeStage,
      isSupport: false,
      layoutX: CANVAS_PADDING + nodeStage * (NODE_WIDTH + COLUMN_GAP),
      layoutY: Math.max(CANVAS_PADDING, (mainHeight - groupHeight) / 2 + row * (NODE_HEIGHT + ROW_GAP)),
    };
  });
  const mainById = new Map(positionedMain.map((node) => [node.id, node]));
  const supportByAnchor = new Map<string, WorkflowNode[]>();
  supportNodes.forEach((node) => {
    const connection = edges.find(
      (edge) =>
        (edge.source === node.id && mainIds.has(edge.target)) ||
        (edge.target === node.id && mainIds.has(edge.source)),
    );
    const anchorId = connection
      ? (connection.source === node.id ? connection.target : connection.source)
      : positionedMain[0]?.id;
    if (anchorId) supportByAnchor.set(anchorId, [...(supportByAnchor.get(anchorId) ?? []), node]);
  });

  let maxSupportRows = 0;
  const positionedSupport: PositionedWorkflowNode[] = [];
  supportByAnchor.forEach((nodes, anchorId) => {
    const anchor = mainById.get(anchorId);
    if (!anchor) return;
    maxSupportRows = Math.max(maxSupportRows, nodes.length);
    nodes.forEach((node, index) => {
      positionedSupport.push({
        ...node,
        stage: anchor.stage,
        isSupport: true,
        layoutX: Math.min(width - NODE_WIDTH - CANVAS_PADDING, anchor.layoutX + index * 46),
        layoutY: mainHeight + 48 + index * (NODE_HEIGHT + 18),
      });
    });
  });

  const height = mainHeight + (supportNodes.length > 0 ? 70 + maxSupportRows * (NODE_HEIGHT + 18) : 0);
  return {
    nodes: [...positionedMain, ...positionedSupport],
    edges,
    width,
    height,
    stageCount,
    maxParallel,
    supportCount: supportNodes.length,
    hasCycle,
  };
}

