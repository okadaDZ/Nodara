import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Svg, { Circle, Path, Text as SvgText } from 'react-native-svg';
import { Bot, Braces, Database, FileOutput, GitBranch, ListFilter, Merge, Plus, RotateCcw, Trash2, Wrench, Zap } from 'lucide-react-native';
import { Workflow, WorkflowNode } from '@/types/workflow';
import {
  layoutWorkflow,
  NODE_HEIGHT,
  NODE_WIDTH,
  PositionedWorkflowNode,
} from '@/utils/workflowLayout';

interface WorkflowGraphProps {
  workflow: Workflow;
  onNodePress: (node: WorkflowNode) => void;
  onDeleteNode?: (nodeId: string) => void;
  onAddNode?: () => void;
}

function CanvasNode({
  node,
  incomingCount,
  outgoingCount,
  onPress,
  onDelete,
}: {
  node: PositionedWorkflowNode;
  incomingCount: number;
  outgoingCount: number;
  onPress: () => void;
  onDelete?: () => void;
}) {
  const isMerge = incomingCount > 1;
  const isBranch = outgoingCount > 1;
  const isIterative = /iterat|recursive|repeat|loop/i.test(
    `${node.name} ${node.description} ${node.instructions}`,
  );
  const isCondition = node.type === 'condition';
  const icon = node.type === 'trigger'
    ? <Zap size={16} color="#D97706" />
    : node.type === 'query_builder'
      ? <ListFilter size={16} color="#2563EB" />
    : node.type === 'memory'
      ? <Database size={16} color="#2563EB" />
        : node.type === 'parser'
        ? <Braces size={16} color="#7C3AED" />
        : node.type === 'tool'
          ? <Wrench size={16} color="#0F8A73" />
          : node.type === 'output'
            ? <FileOutput size={16} color="#C2415B" />
            : isCondition
              ? <GitBranch size={16} color="#0F8A73" />
              : isIterative
                ? <RotateCcw size={16} color="#5E5862" />
                : isMerge
                  ? <Merge size={16} color="#5E5862" />
                  : <Bot size={16} color="#FF6D5A" />;

  return (
    <TouchableOpacity
      activeOpacity={0.82}
      style={[styles.node, node.isSupport && styles.supportNode, isCondition && styles.conditionNode, { left: node.layoutX, top: node.layoutY }]}
      onPress={onPress}
    >
      <View style={styles.nodeHeader}>
        <View style={[styles.nodeIcon, (isMerge || isIterative) && styles.mergeIcon, node.isSupport && styles.supportIcon]}>
          {icon}
        </View>
        <Text style={styles.nodeTitle} numberOfLines={1}>{node.name}</Text>
        {onDelete ? (
          <TouchableOpacity
            style={styles.deleteButton}
            hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}
            onPress={(event) => {
              event.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 size={14} color="#A59FA8" />
          </TouchableOpacity>
        ) : null}
      </View>

      <Text style={styles.nodeDescription} numberOfLines={2}>
        {node.description || 'Tap to configure this agent'}
      </Text>

      <View style={styles.nodeFooter}>
        {node.isSupport ? null : <View style={[styles.statusDot, !node.instructions && styles.statusDotEmpty]} />}
        <Text style={styles.statusText}>{node.isSupport ? node.type : node.instructions ? 'Ready' : 'Needs prompt'}</Text>
        {isBranch ? (
          <View style={styles.branchBadge}>
            <GitBranch size={11} color="#B9502E" />
            <Text style={styles.branchText}>{outgoingCount} paths</Text>
          </View>
        ) : null}
        {isIterative ? (
          <View style={styles.loopBadge}>
            <RotateCcw size={10} color="#6553CF" />
            <Text style={styles.loopText}>bounded loop</Text>
          </View>
        ) : null}
      </View>
    </TouchableOpacity>
  );
}

export const WorkflowGraph: React.FC<WorkflowGraphProps> = ({
  workflow,
  onNodePress,
  onDeleteNode,
  onAddNode,
}) => {
  const layout = useMemo(() => layoutWorkflow(workflow), [workflow]);
  const nodeById = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes],
  );
  const incomingCount = useMemo(() => {
    const counts = new Map<string, number>();
    layout.edges.forEach((edge) => counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1));
    return counts;
  }, [layout.edges]);
  const outgoingCount = useMemo(() => {
    const counts = new Map<string, number>();
    layout.edges.forEach((edge) => counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1));
    return counts;
  }, [layout.edges]);

  return (
    <View style={styles.wrapper}>
      <View style={styles.toolbar}>
        <View>
          <Text style={styles.toolbarLabel}>WORKFLOW MAP</Text>
          <Text style={styles.toolbarMeta}>
            {workflow.nodes.length} nodes · {layout.stageCount} stages
            {layout.maxParallel > 1 ? ` · up to ${layout.maxParallel} parallel` : ''}
            {layout.supportCount > 0 ? ` · ${layout.supportCount} attachments` : ''}
          </Text>
        </View>
        {onAddNode ? (
          <TouchableOpacity style={styles.addButton} onPress={onAddNode}>
            <Plus size={16} color="#FFFFFF" />
            <Text style={styles.addButtonText}>Node</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      {layout.hasCycle ? (
        <View style={styles.cycleWarning}>
          <Text style={styles.cycleWarningText}>This flow contains a cycle. Check its connections before running.</Text>
        </View>
      ) : null}

      <ScrollView
        horizontal
        nestedScrollEnabled
        showsHorizontalScrollIndicator
        contentContainerStyle={styles.horizontalScroll}
      >
        <View style={[styles.canvas, { width: layout.width, height: layout.height }]}>
          <View style={styles.dotLayer} pointerEvents="none">
            {Array.from({ length: Math.ceil(layout.width / 18) * Math.ceil(layout.height / 18) }, (_, index) => (
              <View key={index} style={styles.dot} />
            ))}
          </View>

          <Svg width={layout.width} height={layout.height} style={StyleSheet.absoluteFill} pointerEvents="none">
            {layout.edges.map((edge) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              if (!source || !target) return null;
              const auxiliary = ['tool', 'memory', 'parser'].includes(edge.kind ?? 'flow') || source.isSupport || target.isSupport;
              const startX = auxiliary ? source.layoutX + NODE_WIDTH / 2 : source.layoutX + NODE_WIDTH;
              const startY = auxiliary ? source.layoutY + (source.isSupport ? 0 : NODE_HEIGHT) : source.layoutY + NODE_HEIGHT / 2;
              const endX = auxiliary ? target.layoutX + NODE_WIDTH / 2 : target.layoutX;
              const endY = auxiliary ? target.layoutY + (target.isSupport ? 0 : NODE_HEIGHT) : target.layoutY + NODE_HEIGHT / 2;
              const bend = Math.max(35, Math.abs(endX - startX) * 0.5);
              const path = auxiliary
                ? `M ${startX} ${startY} C ${startX} ${startY - 34}, ${endX} ${endY + 34}, ${endX} ${endY}`
                : `M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`;
              return (
                <React.Fragment key={edge.id}>
                  <Path d={path} stroke={auxiliary ? '#8F86A0' : '#B8B0BA'} strokeWidth={2} strokeDasharray={auxiliary ? '5 5' : undefined} fill="none" />
                  <Circle cx={startX} cy={startY} r={4} fill="#FFFFFF" stroke="#FF6D5A" strokeWidth={2} />
                  <Circle cx={endX} cy={endY} r={4} fill="#FF6D5A" />
                  {edge.label ? (
                    <SvgText x={(startX + endX) / 2} y={(startY + endY) / 2 - 7} fill="#756F79" fontSize="10" fontWeight="600" textAnchor="middle">
                      {edge.label}
                    </SvgText>
                  ) : null}
                </React.Fragment>
              );
            })}
          </Svg>

          {layout.nodes.map((node) => (
            <CanvasNode
              key={node.id}
              node={node}
              incomingCount={incomingCount.get(node.id) ?? 0}
              outgoingCount={outgoingCount.get(node.id) ?? 0}
              onPress={() => onNodePress(node)}
              onDelete={onDeleteNode ? () => onDeleteNode(node.id) : undefined}
            />
          ))}

          {workflow.nodes.length === 0 ? (
            <View style={styles.emptyCanvas}>
              <Plus size={24} color="#B9502E" />
              <Text style={styles.emptyTitle}>Start with a node</Text>
            </View>
          ) : null}
        </View>
      </ScrollView>

      <Text style={styles.scrollHint}>Swipe sideways to explore every stage · stacked nodes run in parallel</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  wrapper: { marginHorizontal: -20 },
  toolbar: { paddingHorizontal: 20, marginBottom: 12, flexDirection: 'row', alignItems: 'center' },
  toolbarLabel: { color: '#756F79', fontSize: 11, fontWeight: '700' },
  toolbarMeta: { color: '#29262D', fontSize: 13, fontWeight: '700', marginTop: 3 },
  addButton: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 9, backgroundColor: '#FF6D5A', borderRadius: 12 },
  addButtonText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
  cycleWarning: { marginHorizontal: 20, marginBottom: 10, borderRadius: 10, backgroundColor: '#FFF8E8', padding: 10, borderWidth: 1, borderColor: '#F3D49E' },
  cycleWarningText: { color: '#8A5B10', fontSize: 12 },
  horizontalScroll: { paddingHorizontal: 20 },
  canvas: { overflow: 'hidden', borderRadius: 14, backgroundColor: '#F1EFEC', borderWidth: 1, borderColor: '#D4CEC8' },
  dotLayer: { position: 'absolute', top: 12, right: 12, bottom: 12, left: 12, flexDirection: 'row', flexWrap: 'wrap', gap: 16, overflow: 'hidden' },
  dot: { width: 2, height: 2, borderRadius: 1, backgroundColor: '#CEC8C3' },
  node: { position: 'absolute', width: NODE_WIDTH, height: NODE_HEIGHT, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#CFC8C2', borderRadius: 10, padding: 12 },
  nodeHeader: { flexDirection: 'row', alignItems: 'center' },
  nodeIcon: { width: 28, height: 28, borderRadius: 8, backgroundColor: '#FFF0ED', alignItems: 'center', justifyContent: 'center', marginRight: 8 },
  mergeIcon: { backgroundColor: '#EEEAE7' },
  supportNode: { borderStyle: 'dashed', borderColor: '#9C92A5', backgroundColor: '#FAF9FB' },
  conditionNode: { borderColor: '#7EC7B9', backgroundColor: '#F2FBF8' },
  supportIcon: { backgroundColor: '#F0EEF3' },
  nodeTitle: { flex: 1, color: '#29262D', fontSize: 13, fontWeight: '800' },
  deleteButton: { padding: 3 },
  nodeDescription: { color: '#756F79', fontSize: 11, lineHeight: 15, marginTop: 8, minHeight: 30 },
  nodeFooter: { flexDirection: 'row', alignItems: 'center', marginTop: 'auto' },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#42A879', marginRight: 5 },
  statusDotEmpty: { backgroundColor: '#E0A13A' },
  statusText: { color: '#756F79', fontSize: 10, fontWeight: '600' },
  branchBadge: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#FFF0ED', paddingHorizontal: 6, paddingVertical: 3, borderRadius: 6 },
  branchText: { color: '#B9502E', fontSize: 9, fontWeight: '700' },
  loopBadge: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#EEEAE7', paddingHorizontal: 6, paddingVertical: 3, borderRadius: 6 },
  loopText: { color: '#5E5862', fontSize: 9, fontWeight: '700' },
  emptyCanvas: { position: 'absolute', left: 0, right: 0, top: 120, alignItems: 'center', gap: 8 },
  emptyTitle: { color: '#29262D', fontWeight: '700' },
  scrollHint: { color: '#8B858E', fontSize: 10, textAlign: 'center', marginTop: 9 },
});
