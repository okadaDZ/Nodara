import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
  Platform,
  SafeAreaView,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@/services/api';
import { Workflow, WorkflowNode, WorkflowRun } from '@/types/workflow';
import { WorkflowGraph } from '@/components/WorkflowGraph';
import { LoadingOverlay } from '@/components/LoadingOverlay';
import { executionNodeCount, insertNode, removeNodePreservingFlow } from '@/utils/workflowGraphOps';
import { Bot, Check, ChevronDown, ChevronUp, Copy, Download, FileText, History, Play, Plus, Save, SlidersHorizontal, X } from 'lucide-react-native';

export default function WorkflowScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [overlayLoading, setOverlayLoading] = useState(false);
  const [overlayMsg, setOverlayMsg] = useState('Updating workflow...');
  const [savingWorkflow, setSavingWorkflow] = useState(false);
  const [workflowSaved, setWorkflowSaved] = useState(false);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState('');
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  // Prompt edit sheet
  const [aiModalVisible, setAiModalVisible] = useState(false);
  const [aiInstruction, setAiInstruction] = useState('');

  // Add Agent Modal
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [newAgentName, setNewAgentName] = useState('');
  const [newAgentDesc, setNewAgentDesc] = useState('');
  const [newAgentParentIds, setNewAgentParentIds] = useState<string[]>([]);
  const [newAgentSuccessorIds, setNewAgentSuccessorIds] = useState<string[]>([]);
  const [newAgentType, setNewAgentType] = useState('agent');

  // n8n Export Modal
  const [n8nModalVisible, setN8nModalVisible] = useState(false);
  const [n8nJson, setN8nJson] = useState('');
  const [n8nLoading, setN8nLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadWorkflow = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await api.getWorkflow(id);
      setWorkflow(data);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Could not load workflow');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadWorkflow();
  }, [loadWorkflow]);

  const loadRuns = useCallback(async () => {
    if (!id) return;
    try {
      setRunsError('');
      setRunsLoading(true);
      setRuns(await api.listWorkflowRuns(id));
    } catch (err: any) {
      setRunsError(err.message || 'Could not load run history.');
    } finally {
      setRunsLoading(false);
    }
  }, [id]);

  useFocusEffect(useCallback(() => {
    loadRuns();
  }, [loadRuns]));

  const openRunReport = async (runId: string) => {
    try {
      await Linking.openURL(await api.getRunReportUrl(runId));
    } catch (err: any) {
      Alert.alert('Report unavailable', err.message || 'Could not open this run report.');
    }
  };

  const openAllRunsReport = async () => {
    if (!id) return;
    try {
      await Linking.openURL(await api.getWorkflowRunsReportUrl(id));
    } catch (err: any) {
      Alert.alert('Report unavailable', err.message || 'Could not open the workflow report.');
    }
  };

  const formatRunDate = (value: string) => new Date(value).toLocaleString([], {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });

  const handleNodePress = (node: WorkflowNode) => {
    router.push({
      pathname: `/agent/${node.id}`,
      params: { workflowId: id },
    });
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (!workflow) return;
    const node = workflow.nodes.find((candidate) => candidate.id === nodeId);
    if (!node) return;
    if (!['tool', 'memory', 'parser'].includes(node.type) && executionNodeCount(workflow) <= 1) {
      Alert.alert('Cannot Delete', 'A workflow must have at least one agent.');
      return;
    }
    const updatedWorkflow = removeNodePreservingFlow(workflow, nodeId);

    try {
      setOverlayLoading(true);
      setOverlayMsg('Updating workflow...');
      const saved = await api.updateWorkflow(updatedWorkflow);
      setWorkflow(saved);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Could not delete node.');
    } finally {
      setOverlayLoading(false);
    }
  };

  const handleAiEdit = async () => {
    if (!id || !aiInstruction.trim()) return;
    try {
      setAiModalVisible(false);
      setOverlayLoading(true);
      setOverlayMsg('Updating nodes and connections…');
      const updated = await api.aiEditWorkflow(id, aiInstruction.trim());
      setWorkflow(updated);
      setAiInstruction('');
    } catch (err: any) {
      Alert.alert('AI Edit Failed', err.message || 'Could not modify workflow.');
    } finally {
      setOverlayLoading(false);
    }
  };

  const handleSaveWorkflow = async () => {
    if (!workflow) return;
    try {
      setSavingWorkflow(true);
      setWorkflowSaved(false);
      const saved = await api.updateWorkflow(workflow);
      setWorkflow(saved);
      setWorkflowSaved(true);
      setTimeout(() => setWorkflowSaved(false), 2000);
    } catch (err: any) {
      Alert.alert('Save Failed', err.message || 'Could not save this workflow.');
    } finally {
      setSavingWorkflow(false);
    }
  };

  const handleAddAgent = async () => {
    if (!workflow || !newAgentName.trim()) {
      Alert.alert('Required', 'Please enter an agent title.');
      return;
    }
    if (['tool', 'memory', 'parser'].includes(newAgentType) && newAgentParentIds.length !== 1) {
      Alert.alert('Choose an agent', 'A support node must be attached to exactly one workflow agent.');
      return;
    }

    const newNodeId = `node_${Date.now().toString(36)}`;
    const newNode: WorkflowNode = {
      id: newNodeId,
      type: newAgentType,
      name: newAgentName.trim(),
      description: newAgentDesc.trim(),
      instructions: '',
    };

    const updatedWorkflow = insertNode(workflow, newNode, newAgentParentIds, newAgentSuccessorIds);

    try {
      setAddModalVisible(false);
      setOverlayLoading(true);
      setOverlayMsg('Adding agent...');
      const saved = await api.updateWorkflow(updatedWorkflow);
      setWorkflow(saved);
      setNewAgentName('');
      setNewAgentDesc('');
      setNewAgentParentIds([]);
      setNewAgentSuccessorIds([]);
      setNewAgentType('agent');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Could not add agent.');
    } finally {
      setOverlayLoading(false);
    }
  };

  // ── n8n Export ──────────────────────────────────────────────────────────
  const handleOpenN8nExport = async () => {
    if (!id) return;
    try {
      setN8nLoading(true);
      setN8nModalVisible(true);
      const json = await api.exportToN8n(id);
      setN8nJson(json);
    } catch (err: any) {
      setN8nModalVisible(false);
      Alert.alert('Export Failed', err.message || 'Could not generate n8n export.');
    } finally {
      setN8nLoading(false);
    }
  };

  const handleCopyN8n = async () => {
    if (!n8nJson) return;
    try {
      await Clipboard.setStringAsync(n8nJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err: any) {
      Alert.alert('Copy Failed', err.message || 'Could not copy the workflow JSON.');
    }
  };

  const handleShareN8n = async () => {
    if (!n8nJson) return;
    try {
      await Share.share({
        message: n8nJson,
        title: `${workflow?.name ?? 'Workflow'} — n8n export`,
      });
    } catch (err: any) {
      Alert.alert('Share Failed', err.message);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6D5A" />
        <Text style={styles.loadingText}>Loading workflow...</Text>
      </SafeAreaView>
    );
  }

  if (!workflow) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <Text style={styles.errorText}>Workflow not found.</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>{workflow.name}</Text>
          {workflow.description ? (
            <Text style={styles.subtitle}>{workflow.description}</Text>
          ) : null}
        </View>

        <WorkflowGraph
          workflow={workflow}
          onNodePress={handleNodePress}
          onDeleteNode={handleDeleteNode}
          onAddNode={() => setAddModalVisible(true)}
        />

        <View style={styles.actionContainer}>
          <TouchableOpacity
            activeOpacity={0.8}
            style={styles.aiEditButton}
            onPress={() => setAiModalVisible(true)}
          >
            <SlidersHorizontal size={18} color="#29262D" />
            <Text style={styles.aiEditText}>Edit with a prompt</Text>
          </TouchableOpacity>

          <TouchableOpacity
            activeOpacity={0.8}
            style={styles.n8nButton}
            onPress={handleOpenN8nExport}
          >
            <Download size={18} color="#FB923C" />
            <Text style={styles.n8nButtonText}>Export to n8n</Text>
          </TouchableOpacity>

        </View>

        <View style={styles.runHistorySection}>
          <View style={styles.runHistoryHeader}>
            <View style={styles.runHistoryTitleRow}>
              <History size={19} color="#29262D" />
              <View>
                <Text style={styles.runHistoryTitle}>Run history</Text>
                <Text style={styles.runHistoryCount}>{runs.length} {runs.length === 1 ? 'saved run' : 'saved runs'}</Text>
              </View>
            </View>
            {runs.length > 0 ? (
              <TouchableOpacity
                style={styles.allReportsButton}
                onPress={openAllRunsReport}
                accessibilityRole="button"
                accessibilityLabel="Open PDF report for all workflow runs"
              >
                <FileText size={15} color="#B9502E" />
                <Text style={styles.allReportsText}>All runs PDF</Text>
              </TouchableOpacity>
            ) : null}
          </View>

          {runsLoading ? (
            <View style={styles.runHistoryMessage}>
              <ActivityIndicator color="#FF6D5A" />
              <Text style={styles.runHistoryMessageText}>Loading saved runs…</Text>
            </View>
          ) : runsError ? (
            <View style={styles.runHistoryMessage}>
              <Text style={styles.runHistoryError}>{runsError}</Text>
              <TouchableOpacity onPress={loadRuns} accessibilityRole="button">
                <Text style={styles.retryRunsText}>Try again</Text>
              </TouchableOpacity>
            </View>
          ) : runs.length === 0 ? (
            <View style={styles.runHistoryEmpty}>
              <Text style={styles.runHistoryEmptyTitle}>No runs yet</Text>
              <Text style={styles.runHistoryMessageText}>Run this workflow and its input, agent results, and final output will appear here.</Text>
            </View>
          ) : (
            <View style={styles.runList}>
              {runs.map((run) => {
                const expanded = expandedRunId === run.id;
                const completedNodes = run.nodes.filter((node) => node.status === 'completed').length;
                return (
                  <View key={run.id} style={styles.runRow}>
                    <TouchableOpacity
                      style={styles.runRowHeader}
                      onPress={() => setExpandedRunId(expanded ? null : run.id)}
                      accessibilityRole="button"
                      accessibilityState={{ expanded }}
                      accessibilityLabel={`${run.status} run from ${formatRunDate(run.created_at)}`}
                    >
                      <View style={[styles.runStatusDot, run.status === 'completed' ? styles.runStatusComplete : run.status === 'failed' ? styles.runStatusFailed : styles.runStatusActive]} />
                      <View style={styles.runRowCopy}>
                        <Text style={styles.runDate}>{formatRunDate(run.created_at)}</Text>
                        <Text style={styles.runMeta}>{run.status} · {completedNodes} of {run.nodes.length} agents completed</Text>
                      </View>
                      {expanded ? <ChevronUp size={18} color="#756F79" /> : <ChevronDown size={18} color="#756F79" />}
                    </TouchableOpacity>

                    {expanded ? (
                      <View style={styles.runDetails}>
                        <Text style={styles.runDetailLabel}>Input</Text>
                        <Text style={styles.runDetailText} selectable>{run.input || 'No input saved.'}</Text>
                        <Text style={styles.runDetailLabel}>Final output</Text>
                        <Text style={styles.runDetailText} selectable>{run.final_output || run.error || 'No final output was produced.'}</Text>

                        <Text style={styles.runDetailLabel}>Agent results</Text>
                        {run.nodes.map((node) => (
                          <View key={node.id} style={styles.nodeResultRow}>
                            <View style={styles.nodeResultHeader}>
                              <Text style={styles.nodeResultName}>{node.node_name}</Text>
                              <Text style={styles.nodeResultStatus}>{node.status}</Text>
                            </View>
                            <Text style={styles.nodeResultText} selectable>{node.output || node.error || 'No output saved.'}</Text>
                          </View>
                        ))}

                        <TouchableOpacity
                          style={styles.runReportButton}
                          onPress={() => openRunReport(run.id)}
                          accessibilityRole="button"
                          accessibilityLabel={`Open PDF report for run from ${formatRunDate(run.created_at)}`}
                        >
                          <FileText size={16} color="#B9502E" />
                          <Text style={styles.runReportText}>Open run PDF</Text>
                        </TouchableOpacity>
                      </View>
                    ) : null}
                  </View>
                );
              })}
            </View>
          )}
        </View>
      </ScrollView>

      <View style={styles.bottomDock}>
        <TouchableOpacity
          activeOpacity={0.82}
          style={[styles.saveWorkflowButton, workflowSaved && styles.saveWorkflowButtonSaved]}
          onPress={handleSaveWorkflow}
          disabled={savingWorkflow}
        >
          {savingWorkflow ? <ActivityIndicator size="small" color="#FFFFFF" /> : workflowSaved ? <Check size={19} color="#FFFFFF" /> : <Save size={19} color="#FFFFFF" />}
          <Text style={styles.saveWorkflowText}>{savingWorkflow ? 'Saving…' : workflowSaved ? 'Saved' : 'Save'}</Text>
        </TouchableOpacity>
        <TouchableOpacity activeOpacity={0.82} style={styles.runButton} onPress={() => router.push(`/run/${workflow.id}`)}>
          <Play size={19} color="#FFFFFF" fill="#FFFFFF" />
          <Text style={styles.runButtonText}>Run</Text>
        </TouchableOpacity>
      </View>

      {/* Prompt edit sheet */}
      <Modal visible={aiModalVisible} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <View style={styles.modalHeaderTitleRow}>
                <SlidersHorizontal size={20} color="#29262D" />
                <Text style={styles.modalTitle}>Edit with a prompt</Text>
              </View>
              <TouchableOpacity onPress={() => setAiModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSub}>
              Describe the structural change. Existing connections are preserved where possible.
            </Text>

            <TextInput
              style={styles.modalInput}
              placeholder="e.g. Add a fact-checker agent between research and summary"
              placeholderTextColor="#64748B"
              multiline
              numberOfLines={3}
              value={aiInstruction}
              onChangeText={setAiInstruction}
            />

            <TouchableOpacity
              style={[styles.modalSubmitButton, !aiInstruction.trim() && styles.modalDisabledButton]}
              onPress={handleAiEdit}
              disabled={!aiInstruction.trim()}
            >
              <Text style={styles.modalSubmitText}>Apply change</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Add Agent Modal */}
      <Modal visible={addModalVisible} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, styles.addModalCard]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add workflow node</Text>
              <TouchableOpacity onPress={() => setAddModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView
              style={styles.addModalScroll}
              contentContainerStyle={styles.addModalScrollContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator
            >
            <Text style={styles.inputLabel}>Agent Name</Text>
            <TextInput
              style={styles.modalSingleInput}
              placeholder="e.g. Fact Checker, Translator, Critic"
              placeholderTextColor="#64748B"
              value={newAgentName}
              onChangeText={setNewAgentName}
            />

            <Text style={styles.inputLabel}>Node type</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.parentOptions}>
              {['trigger', 'query_builder', 'agent', 'condition', 'action', 'output', 'tool', 'memory', 'parser'].map((type) => {
                const selected = newAgentType === type;
                return (
                  <TouchableOpacity
                    key={type}
                    style={[styles.typeOption, selected && styles.typeOptionSelected]}
                    onPress={() => {
                      setNewAgentType(type);
                      if (['tool', 'memory', 'parser'].includes(type)) setNewAgentSuccessorIds([]);
                    }}
                  >
                    <Text style={[styles.typeOptionText, selected && styles.typeOptionTextSelected]}>{type}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <Text style={styles.inputLabel}>Role Description</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="What is this agent responsible for?"
              placeholderTextColor="#64748B"
              multiline
              numberOfLines={3}
              value={newAgentDesc}
              onChangeText={setNewAgentDesc}
            />

            <Text style={styles.inputLabel}>
              {['tool', 'memory', 'parser'].includes(newAgentType) ? 'Attach to' : 'Runs after'}
            </Text>
            <Text style={styles.connectionHelp}>
              {['tool', 'memory', 'parser'].includes(newAgentType)
                ? 'Choose the agent that uses this support node.'
                : 'Select multiple nodes to create a merge. Leave empty to start this node in parallel.'}
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.parentOptions}
            >
              {workflow.nodes.filter((node) => !['tool', 'memory', 'parser'].includes(node.type)).map((node) => {
                const selected = newAgentParentIds.includes(node.id);
                return (
                  <TouchableOpacity
                    key={node.id}
                    style={[styles.parentOption, selected && styles.parentOptionSelected]}
                    onPress={() => setNewAgentParentIds((current) => {
                      if (['tool', 'memory', 'parser'].includes(newAgentType)) {
                        return current.includes(node.id) ? [] : [node.id];
                      }
                      return current.includes(node.id)
                        ? current.filter((nodeId) => nodeId !== node.id)
                        : [...current, node.id];
                    })}
                  >
                    <Text style={[styles.parentOptionText, selected && styles.parentOptionTextSelected]} numberOfLines={1}>
                      {node.name}
                    </Text>
                    {selected ? <Check size={13} color="#FFFFFF" /> : null}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {!['tool', 'memory', 'parser'].includes(newAgentType) ? (
              <>
                <Text style={styles.inputLabel}>Runs before</Text>
                <Text style={styles.connectionHelp}>
                  Choose downstream nodes to insert this node in the middle. Existing direct links are replaced safely.
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.parentOptions}>
                  {workflow.nodes.filter((node) => !['tool', 'memory', 'parser'].includes(node.type)).map((node) => {
                    const selected = newAgentSuccessorIds.includes(node.id);
                    return (
                      <TouchableOpacity
                        key={node.id}
                        style={[styles.parentOption, selected && styles.parentOptionSelected]}
                        onPress={() => setNewAgentSuccessorIds((current) =>
                          current.includes(node.id) ? current.filter((nodeId) => nodeId !== node.id) : [...current, node.id]
                        )}
                      >
                        <Text style={[styles.parentOptionText, selected && styles.parentOptionTextSelected]} numberOfLines={1}>{node.name}</Text>
                        {selected ? <Check size={13} color="#FFFFFF" /> : null}
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </>
            ) : null}
            </ScrollView>

            <TouchableOpacity
              style={[styles.modalSubmitButton, styles.stickySaveButton, !newAgentName.trim() && styles.modalDisabledButton]}
              onPress={handleAddAgent}
              disabled={!newAgentName.trim()}
            >
              <Text style={styles.modalSubmitText}>
                {['tool', 'memory', 'parser'].includes(newAgentType)
                  ? 'Save support node'
                  : newAgentSuccessorIds.length > 0
                    ? 'Save & insert node'
                    : newAgentParentIds.length > 1
                      ? 'Save merge node'
                      : newAgentParentIds.length === 1 ? 'Save connected node' : 'Save parallel node'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* n8n Export Modal */}
      <Modal visible={n8nModalVisible} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, styles.n8nModal]}>
            <View style={styles.modalHeader}>
              <View style={styles.modalHeaderTitleRow}>
                <Download size={20} color="#FB923C" />
                <Text style={styles.modalTitle}>Export to n8n</Text>
              </View>
              <TouchableOpacity onPress={() => { setN8nModalVisible(false); setCopied(false); }}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            {n8nLoading ? (
              <View style={styles.n8nLoadingRow}>
                <ActivityIndicator color="#FB923C" />
                <Text style={styles.n8nLoadingText}>Generating n8n JSON…</Text>
              </View>
            ) : (
              <>
                <Text style={styles.modalSub}>
                  Copy the JSON below and paste it into n8n via{' '}
                  <Text style={styles.n8nHighlight}>Import from JSON</Text> in your workflow editor.
                </Text>

                {/* Instructions row */}
                <View style={styles.n8nSteps}>
                  {['Open n8n', 'New Workflow → ⋮ menu', 'Import from JSON', 'Paste & Save'].map(
                    (step, i) => (
                      <View key={i} style={styles.n8nStep}>
                        <View style={styles.n8nStepNum}>
                          <Text style={styles.n8nStepNumText}>{i + 1}</Text>
                        </View>
                        <Text style={styles.n8nStepLabel}>{step}</Text>
                      </View>
                    )
                  )}
                </View>

                {/* JSON preview */}
                <ScrollView style={styles.n8nJsonScroll} nestedScrollEnabled>
                  <Text style={styles.n8nJsonText} selectable>
                    {n8nJson.slice(0, 1200)}{n8nJson.length > 1200 ? '\n…(truncated preview)' : ''}
                  </Text>
                </ScrollView>

                {/* Action buttons */}
                <View style={styles.n8nActions}>
                  <TouchableOpacity
                    activeOpacity={0.8}
                    style={styles.copyButton}
                    onPress={handleCopyN8n}
                  >
                    {copied ? (
                      <Check size={18} color="#10B981" />
                    ) : (
                      <Copy size={18} color="#F8FAFC" />
                    )}
                    <Text style={[styles.copyButtonText, copied && { color: '#10B981' }]}>
                      {copied ? 'Copied!' : 'Copy JSON'}
                    </Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    activeOpacity={0.8}
                    style={styles.shareButton}
                    onPress={handleShareN8n}
                  >
                    <Text style={styles.shareButtonText}>Share…</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      <LoadingOverlay visible={overlayLoading} message={overlayMsg} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F7F5F2' },
  loadingContainer: { flex: 1, backgroundColor: '#F7F5F2', justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: '#756F79', marginTop: 12, fontSize: 15 },
  errorText: { color: '#EF4444', fontSize: 16 },
  scrollContent: { padding: 20, paddingBottom: 48 },
  header: { marginBottom: 20 },
  title: { color: '#29262D', fontSize: 28, fontWeight: '800', letterSpacing: -0.7, marginBottom: 5 },
  subtitle: { color: '#756F79', fontSize: 14, lineHeight: 20 },
  actionContainer: { marginTop: 20, marginBottom: 10, flexDirection: 'row', gap: 10 },
  runHistorySection: { marginTop: 28, paddingTop: 22, borderTopWidth: 1, borderTopColor: '#DDD8D3' },
  runHistoryHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14 },
  runHistoryTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1 },
  runHistoryTitle: { color: '#29262D', fontSize: 18, fontWeight: '800', letterSpacing: -0.3 },
  runHistoryCount: { color: '#756F79', fontSize: 11, marginTop: 2 },
  allReportsButton: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 4 },
  allReportsText: { color: '#B9502E', fontSize: 12, fontWeight: '700' },
  runHistoryMessage: { minHeight: 96, alignItems: 'center', justifyContent: 'center', gap: 9 },
  runHistoryMessageText: { color: '#756F79', fontSize: 12, lineHeight: 18, textAlign: 'center' },
  runHistoryError: { color: '#B42318', fontSize: 12, lineHeight: 18, textAlign: 'center' },
  retryRunsText: { color: '#B9502E', fontSize: 12, fontWeight: '800', paddingVertical: 8 },
  runHistoryEmpty: { minHeight: 112, paddingHorizontal: 28, alignItems: 'center', justifyContent: 'center', backgroundColor: '#EEEAE6', borderRadius: 14 },
  runHistoryEmptyTitle: { color: '#29262D', fontSize: 14, fontWeight: '800', marginBottom: 5 },
  runList: { borderWidth: 1, borderColor: '#DDD8D3', borderRadius: 14, overflow: 'hidden', backgroundColor: '#FFFFFF' },
  runRow: { borderBottomWidth: 1, borderBottomColor: '#EEEAE7' },
  runRowHeader: { minHeight: 68, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center' },
  runStatusDot: { width: 10, height: 10, borderRadius: 5, marginRight: 11 },
  runStatusComplete: { backgroundColor: '#35A978' },
  runStatusFailed: { backgroundColor: '#D94A43' },
  runStatusActive: { backgroundColor: '#F59E0B' },
  runRowCopy: { flex: 1, minWidth: 0, paddingRight: 8 },
  runDate: { color: '#29262D', fontSize: 13, fontWeight: '700' },
  runMeta: { color: '#756F79', fontSize: 11, marginTop: 3, textTransform: 'capitalize' },
  runDetails: { paddingHorizontal: 14, paddingBottom: 15, backgroundColor: '#FAF8F6' },
  runDetailLabel: { color: '#756F79', fontSize: 10, fontWeight: '800', marginTop: 12, marginBottom: 5 },
  runDetailText: { color: '#29262D', fontSize: 12, lineHeight: 18 },
  nodeResultRow: { paddingVertical: 9, borderTopWidth: 1, borderTopColor: '#E8E3DF' },
  nodeResultHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 },
  nodeResultName: { color: '#29262D', fontSize: 12, fontWeight: '700', flex: 1 },
  nodeResultStatus: { color: '#756F79', fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  nodeResultText: { color: '#5E5862', fontSize: 11, lineHeight: 16 },
  runReportButton: { minHeight: 44, marginTop: 10, borderTopWidth: 1, borderTopColor: '#E8E3DF', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 },
  runReportText: { color: '#B9502E', fontSize: 12, fontWeight: '800' },
  aiEditButton: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#FFFFFF', borderRadius: 11, paddingVertical: 12, paddingHorizontal: 10,
    borderWidth: 1, borderColor: '#DDD8D3', gap: 8,
  },
  aiEditText: { color: '#29262D', fontSize: 12, fontWeight: '700' },
  bottomDock: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 10, paddingBottom: 8, backgroundColor: '#F7F5F2', borderTopWidth: 1, borderTopColor: '#E3DEDA' },
  saveWorkflowButton: {
    flex: 1, minHeight: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#29262D', borderRadius: 12, gap: 8,
  },
  saveWorkflowButtonSaved: { backgroundColor: '#2F8F68' },
  saveWorkflowText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  n8nButton: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#FFFFFF', borderRadius: 11, paddingVertical: 12, paddingHorizontal: 10,
    borderWidth: 1, borderColor: '#DDD8D3', gap: 8,
  },
  n8nButtonText: { color: '#B9502E', fontSize: 12, fontWeight: '700' },
  runButton: {
    flex: 1, minHeight: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#FF6D5A', borderRadius: 12, gap: 8,
  },
  runButtonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(41, 38, 45, 0.45)', justifyContent: 'flex-end' },
  modalCard: {
    backgroundColor: '#F7F5F2', borderTopLeftRadius: 22, borderTopRightRadius: 22,
    padding: 24, borderWidth: 1, borderColor: '#DDD8D3',
  },
  addModalCard: { maxHeight: '90%', paddingBottom: 16 },
  addModalScroll: { flexShrink: 1 },
  addModalScrollContent: { paddingBottom: 4 },
  stickySaveButton: { marginTop: 12 },
  n8nModal: { maxHeight: '88%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  modalHeaderTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  modalTitle: { color: '#29262D', fontSize: 18, fontWeight: '700' },
  modalSub: { color: '#756F79', fontSize: 13, marginBottom: 16, lineHeight: 18 },
  modalInput: {
    backgroundColor: '#FFFFFF', borderRadius: 10, borderWidth: 1, borderColor: '#D8D2CC',
    color: '#29262D', padding: 12, fontSize: 15, minHeight: 80,
    textAlignVertical: 'top', marginBottom: 16,
  },
  modalSingleInput: {
    backgroundColor: '#FFFFFF', borderRadius: 10, borderWidth: 1, borderColor: '#D8D2CC',
    color: '#29262D', padding: 12, fontSize: 15, marginBottom: 12,
  },
  inputLabel: { color: '#29262D', fontSize: 12, fontWeight: '700', marginBottom: 6 },
  connectionHelp: { color: '#756F79', fontSize: 12, lineHeight: 17, marginBottom: 10 },
  parentOptions: { gap: 8, paddingBottom: 18 },
  parentOption: {
    maxWidth: 170, flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D8D2CC',
    borderRadius: 10, paddingHorizontal: 11, paddingVertical: 9,
  },
  parentOptionSelected: { backgroundColor: '#29262D', borderColor: '#29262D' },
  parentOptionText: { color: '#5E5862', fontSize: 12, fontWeight: '600', maxWidth: 125 },
  parentOptionTextSelected: { color: '#FFFFFF' },
  typeOption: {
    borderRadius: 8, borderWidth: 1, borderColor: '#D8D2CC',
    backgroundColor: '#FFFFFF', paddingHorizontal: 11, paddingVertical: 7,
  },
  typeOptionSelected: { backgroundColor: '#FF6D5A', borderColor: '#FF9B8E' },
  typeOptionText: { color: '#5E5862', fontSize: 11, fontWeight: '700', textTransform: 'capitalize' },
  typeOptionTextSelected: { color: '#FFFFFF' },
  modalSubmitButton: { backgroundColor: '#FF6D5A', borderRadius: 11, paddingVertical: 14, alignItems: 'center' },
  modalDisabledButton: { backgroundColor: '#B8B0BA' },
  modalSubmitText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
  // n8n export modal styles
  n8nHighlight: { color: '#FB923C', fontWeight: '600' },
  n8nLoadingRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 24 },
  n8nLoadingText: { color: '#756F79', fontSize: 14 },
  n8nSteps: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16, gap: 4 },
  n8nStep: { flex: 1, alignItems: 'center', gap: 6 },
  n8nStepNum: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: 'rgba(251, 146, 60, 0.15)',
    borderWidth: 1, borderColor: '#FB923C',
    justifyContent: 'center', alignItems: 'center',
  },
  n8nStepNumText: { color: '#FB923C', fontSize: 13, fontWeight: '700' },
  n8nStepLabel: { color: '#756F79', fontSize: 10, textAlign: 'center', lineHeight: 13 },
  n8nJsonScroll: {
    backgroundColor: '#0F172A', borderRadius: 10, borderWidth: 1,
    borderColor: '#1E293B', padding: 12, maxHeight: 180, marginBottom: 16,
  },
  n8nJsonText: { color: '#4ADE80', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 11, lineHeight: 16 },
  n8nActions: { flexDirection: 'row', gap: 10 },
  copyButton: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#29262D', borderRadius: 10, paddingVertical: 13,
    borderWidth: 1, borderColor: '#29262D', gap: 6,
  },
  copyButtonText: { color: '#F8FAFC', fontSize: 14, fontWeight: '600' },
  shareButton: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#292524', borderRadius: 12, paddingVertical: 13,
    borderWidth: 1, borderColor: '#44403C',
  },
  shareButtonText: { color: '#D6D3D1', fontSize: 14, fontWeight: '600' },
});
