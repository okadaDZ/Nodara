import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '@/services/api';
import { AvailableModel, Workflow } from '@/types/workflow';
import { VoiceRecorder } from '@/components/VoiceRecorder';
import { LoadingOverlay } from '@/components/LoadingOverlay';
import { loadSettings } from '@/services/settings';
import { attachSupportNode, rewireIncomingEdges } from '@/utils/workflowGraphOps';
import { Check, Mic, SlidersHorizontal, Wand2, X } from 'lucide-react-native';

export default function AgentEditorScreen() {
  const { id, workflowId } = useLocalSearchParams<{ id: string; workflowId: string }>();
  const router = useRouter();

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [defaultModel, setDefaultModel] = useState('');
  const [globalModel, setGlobalModel] = useState('');
  const [parentIds, setParentIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overlayLoading, setOverlayLoading] = useState(false);
  const [overlayMsg, setOverlayMsg] = useState('Generating instructions...');

  // Voice edit modal state
  const [voiceModalVisible, setVoiceModalVisible] = useState(false);

  // User hint modal for generate
  const [hintModalVisible, setHintModalVisible] = useState(false);
  const [userHint, setUserHint] = useState('');

  const loadAgent = useCallback(async () => {
    if (!workflowId || !id) return;
    try {
      setLoading(true);
      const wf = await api.getWorkflow(workflowId);
      const localSettings = await loadSettings();
      setGlobalModel(localSettings.globalModel);
      setWorkflow(wf);
      const node = wf.nodes.find((n) => n.id === id);
      if (node) {
        setName(node.name);
        setDescription(node.description || '');
        setInstructions(node.instructions || '');
        let catalogModels: AvailableModel[] = [];
        let catalogDefault = node.model || '';
        try {
          const catalog = await api.getModels();
          catalogModels = catalog.models;
          catalogDefault = catalog.default_model;
        } catch {
          // Editing still works offline when the provider catalog is temporarily unavailable.
        }
        const activeModel = node.model_override ? (node.model || catalogDefault) : '';
        if (activeModel && !catalogModels.some((model) => model.id === activeModel)) {
          catalogModels = [{ id: activeModel, name: activeModel }, ...catalogModels];
        }
        setModels(catalogModels);
        setDefaultModel(catalogDefault);
        setSelectedModel(activeModel);
        const isSupport = ['tool', 'memory', 'parser'].includes(node.type);
        setParentIds(isSupport
          ? wf.edges.filter((edge) => edge.source === id && ['tool', 'memory', 'parser'].includes(edge.kind ?? 'flow')).map((edge) => edge.target)
          : wf.edges.filter((edge) => edge.target === id && ['flow', 'conditional'].includes(edge.kind ?? 'flow')).map((edge) => edge.source));
      }
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Could not load agent details.');
    } finally {
      setLoading(false);
    }
  }, [workflowId, id]);

  useEffect(() => {
    loadAgent();
  }, [loadAgent]);

  const handleSave = async () => {
    if (!workflow || !id) return;
    if (!name.trim()) {
      Alert.alert('Required', 'Please enter an agent title.');
      return;
    }

    const updatedNodes = workflow.nodes.map((n) => {
      if (n.id === id) {
        return {
          ...n,
          name: name.trim(),
          description: description.trim(),
          instructions: instructions.trim(),
          model: selectedModel || globalModel || defaultModel || n.model,
          model_override: Boolean(selectedModel),
        };
      }
      return n;
    });

    const editedWorkflow: Workflow = { ...workflow, nodes: updatedNodes };
    const currentNode = updatedNodes.find((node) => node.id === id);
    const updatedWorkflow = currentNode && ['tool', 'memory', 'parser'].includes(currentNode.type)
      ? attachSupportNode(editedWorkflow, id, parentIds[0])
      : rewireIncomingEdges(editedWorkflow, id, parentIds);

    try {
      setSaving(true);
      await api.updateWorkflow(updatedWorkflow);
      router.back();
    } catch (err: any) {
      Alert.alert('Save Failed', err.message || 'Could not save agent updates.');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateInstructions = async () => {
    if (!workflowId || !id) return;
    setHintModalVisible(false);
    try {
      setOverlayLoading(true);
      setOverlayMsg('Drafting instructions…');
      const generated = await api.generateAgentInstructions(workflowId, id, userHint.trim());
      setInstructions(generated);
      setUserHint('');
    } catch (err: any) {
      Alert.alert('Generation Failed', err.message || 'Could not generate instructions.');
    } finally {
      setOverlayLoading(false);
    }
  };

  const handleImproveInstructions = async () => {
    if (!workflowId || !id) return;
    if (!instructions.trim()) {
      Alert.alert('Notice', 'Generate or write instructions first to improve them.');
      return;
    }

    try {
      setOverlayLoading(true);
      setOverlayMsg('Refining instructions…');
      const improved = await api.improveAgentInstructions(workflowId, id, instructions.trim());
      setInstructions(improved);
    } catch (err: any) {
      Alert.alert('Improvement Failed', err.message || 'Could not improve instructions.');
    } finally {
      setOverlayLoading(false);
    }
  };

  const handleVoiceEditComplete = async (audioUri: string) => {
    if (!workflowId || !id) return;
    setVoiceModalVisible(false);
    try {
      setOverlayLoading(true);
      setOverlayMsg('Transcribing and updating instructions...');
      const updated = await api.audioEditAgent(workflowId, id, audioUri);
      setInstructions(updated);
    } catch (err: any) {
      Alert.alert('Voice Edit Failed', err.message || 'Could not update with voice.');
    } finally {
      setOverlayLoading(false);
    }
  };

  const unavailableParentIds = useMemo(() => {
    if (!workflow || !id) return new Set<string>();
    const outgoing = new Map<string, string[]>();
    workflow.edges.forEach((edge) => {
      outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge.target]);
    });
    const descendants = new Set<string>([id]);
    const queue = [id];
    while (queue.length > 0) {
      const current = queue.shift()!;
      for (const target of outgoing.get(current) ?? []) {
        if (!descendants.has(target)) {
          descendants.add(target);
          queue.push(target);
        }
      }
    }
    return descendants;
  }, [workflow, id]);

  const currentNode = workflow?.nodes.find((node) => node.id === id);
  const isSupportNode = currentNode ? ['tool', 'memory', 'parser'].includes(currentNode.type) : false;

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6D5A" />
        <Text style={styles.loadingText}>Loading agent...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <Text style={styles.title}>{name || 'Configure Agent'}</Text>
          <Text style={styles.subtitle}>
            Set its role, model, connections, and working instructions.
          </Text>

          <View style={styles.card}>
            <Text style={styles.inputLabel}>Agent Name</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="e.g. Researcher, Summarizer"
              placeholderTextColor="#8B858E"
            />

            <Text style={styles.inputLabel}>Short Role Description</Text>
            <TextInput
              style={styles.input}
              value={description}
              onChangeText={setDescription}
              placeholder="1-sentence role summary"
              placeholderTextColor="#8B858E"
            />

            <Text style={styles.inputLabel}>AI Model</Text>
            <Text style={styles.connectionHelp}>
              The default is already assigned. Choose another model only for this node.
            </Text>
            {models.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.modelOptions}>
                <TouchableOpacity
                  activeOpacity={0.8}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: !selectedModel }}
                  style={[styles.modelOption, !selectedModel && styles.modelOptionSelected]}
                  onPress={() => setSelectedModel('')}
                >
                  <View style={[styles.modelDot, !selectedModel && styles.modelDotSelected]} />
                  <View>
                    <Text style={[styles.modelOptionText, !selectedModel && styles.modelOptionTextSelected]}>Use global default</Text>
                    <Text style={styles.defaultModelText}>{globalModel || defaultModel || 'Backend managed'}</Text>
                  </View>
                </TouchableOpacity>
                {models.map((model) => {
                  const selected = selectedModel === model.id;
                  const isDefault = defaultModel === model.id;
                  return (
                    <TouchableOpacity
                      key={model.id}
                      activeOpacity={0.8}
                      accessibilityRole="radio"
                      accessibilityState={{ selected }}
                      style={[styles.modelOption, selected && styles.modelOptionSelected]}
                      onPress={() => setSelectedModel(model.id)}
                    >
                      <View style={[styles.modelDot, selected && styles.modelDotSelected]} />
                      <View>
                        <Text style={[styles.modelOptionText, selected && styles.modelOptionTextSelected]} numberOfLines={1}>
                          {model.name}
                        </Text>
                        {isDefault ? <Text style={styles.defaultModelText}>Workflow default</Text> : null}
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            ) : (
              <View style={styles.modelUnavailable}>
                <Text style={styles.modelUnavailableText}>Using backend default model</Text>
              </View>
            )}

            <Text style={styles.inputLabel}>{isSupportNode ? 'Attached to' : 'Runs after'}</Text>
            <Text style={styles.connectionHelp}>
              {isSupportNode
                ? 'Choose the one workflow node that uses this support node.'
                : 'Choose several agents to merge their results here. Choose none to make this a starting agent.'}
            </Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.parentOptions}>
              {workflow?.nodes
                .filter((candidate) => !['tool', 'memory', 'parser'].includes(candidate.type))
                .filter((candidate) => isSupportNode || !unavailableParentIds.has(candidate.id))
                .map((candidate) => {
                  const selected = parentIds.includes(candidate.id);
                  return (
                    <TouchableOpacity
                      key={candidate.id}
                      style={[styles.parentOption, selected && styles.parentOptionSelected]}
                      onPress={() => setParentIds((current) => isSupportNode
                        ? (current.includes(candidate.id) ? [] : [candidate.id])
                        : current.includes(candidate.id)
                          ? current.filter((nodeId) => nodeId !== candidate.id)
                          : [...current, candidate.id]
                      )}
                    >
                      <Text style={[styles.parentOptionText, selected && styles.parentOptionTextSelected]} numberOfLines={1}>
                        {candidate.name}
                      </Text>
                      {selected ? <Check size={13} color="#FFFFFF" /> : null}
                    </TouchableOpacity>
                  );
                })}
            </ScrollView>
          </View>

          <View style={styles.instructionsHeader}>
            <Text style={styles.instructionsTitle}>What should this agent do?</Text>
          </View>

          <View style={styles.card}>
            <TextInput
              style={styles.textArea}
              value={instructions}
              onChangeText={setInstructions}
              placeholder="Describe the step-by-step instructions for this agent to execute..."
              placeholderTextColor="#8B858E"
              multiline
              numberOfLines={8}
              textAlignVertical="top"
            />

            <View style={styles.aiButtonRow}>
              <TouchableOpacity
                activeOpacity={0.8}
                style={styles.magicButton}
                onPress={() => setHintModalVisible(true)}
              >
                <Wand2 size={16} color="#B9502E" />
                <Text style={styles.magicButtonText}>Draft instructions</Text>
              </TouchableOpacity>

              <TouchableOpacity
                activeOpacity={0.8}
                style={[styles.magicButton, styles.magicSecondaryButton]}
                onPress={handleImproveInstructions}
              >
                <SlidersHorizontal size={16} color="#29262D" />
                <Text style={styles.magicSecondaryText}>Improve instructions</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              activeOpacity={0.8}
              style={styles.voiceEditButton}
              onPress={() => setVoiceModalVisible(true)}
            >
              <Mic size={16} color="#5E5862" />
              <Text style={styles.voiceEditText}>Speak to create or update instructions</Text>
            </TouchableOpacity>
          </View>

        </ScrollView>

        <View style={styles.saveDock}>
          <TouchableOpacity
            activeOpacity={0.82}
            style={styles.saveButton}
            onPress={handleSave}
            disabled={saving}
          >
            {saving ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Check size={20} color="#FFFFFF" />}
            <Text style={styles.saveButtonText}>{saving ? 'Saving…' : 'Save node'}</Text>
          </TouchableOpacity>
        </View>

        {/* Voice Modal */}
        <Modal visible={voiceModalVisible} animationType="slide" transparent>
          <View style={styles.modalBackdrop}>
            <View style={styles.voiceModalCard}>
              <VoiceRecorder
                onRecordingComplete={handleVoiceEditComplete}
                onCancel={() => setVoiceModalVisible(false)}
                title="Speak your instructions"
                subtitle="e.g. 'This agent should only look for restaurants with rating above 4.5 and under 200 AED.'"
              />
            </View>
          </View>
        </Modal>

        {/* Generate Hint Modal */}
        <Modal visible={hintModalVisible} animationType="slide" transparent>
          <View style={styles.modalBackdrop}>
            <View style={styles.modalCard}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>AI Instruction Generator</Text>
                <TouchableOpacity onPress={() => setHintModalVisible(false)}>
                  <X size={20} color="#756F79" />
                </TouchableOpacity>
              </View>

              <Text style={styles.modalSub}>
                Optionally provide specific guidelines or constraints for this agent:
              </Text>

              <TextInput
                style={styles.modalInput}
                placeholder="e.g. Keep output strictly under 3 bullet points and verify dates"
                placeholderTextColor="#8B858E"
                multiline
                numberOfLines={3}
                value={userHint}
                onChangeText={setUserHint}
              />

              <TouchableOpacity
                style={styles.modalSubmitButton}
                onPress={handleGenerateInstructions}
              >
                <Text style={styles.modalSubmitText}>Generate Instructions</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        <LoadingOverlay visible={overlayLoading} message={overlayMsg} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F7F5F2',
  },
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#F7F5F2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#756F79',
    marginTop: 12,
    fontSize: 15,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 110,
  },
  title: {
    color: '#29262D',
    fontSize: 28,
    fontWeight: '800',
    marginBottom: 4,
  },
  subtitle: {
    color: '#756F79',
    fontSize: 14,
    marginBottom: 20,
    lineHeight: 20,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    marginBottom: 20,
  },
  inputLabel: {
    color: '#29262D',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 6,
    marginTop: 6,
  },
  connectionHelp: {
    color: '#756F79',
    fontSize: 12,
    lineHeight: 16,
    marginBottom: 9,
  },
  parentOptions: {
    gap: 8,
    paddingBottom: 8,
  },
  modelOptions: {
    gap: 8,
    paddingBottom: 12,
  },
  modelOption: {
    minWidth: 150,
    maxWidth: 220,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    backgroundColor: '#FAF9F7',
    borderWidth: 1,
    borderColor: '#D8D2CC',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  modelOptionSelected: {
    backgroundColor: '#FFF0ED',
    borderColor: '#FF6D5A',
  },
  modelDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: '#A59FA8',
  },
  modelDotSelected: {
    borderColor: '#FF6D5A',
    backgroundColor: '#FF6D5A',
  },
  modelOptionText: {
    maxWidth: 165,
    color: '#5E5862',
    fontSize: 12,
    fontWeight: '700',
  },
  modelOptionTextSelected: {
    color: '#29262D',
  },
  defaultModelText: {
    color: '#B9502E',
    fontSize: 10,
    marginTop: 2,
  },
  modelUnavailable: {
    backgroundColor: '#FAF9F7',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    padding: 11,
    marginBottom: 12,
  },
  modelUnavailableText: {
    color: '#756F79',
    fontSize: 12,
  },
  parentOption: {
    maxWidth: 160,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FAF9F7',
    borderWidth: 1,
    borderColor: '#D8D2CC',
    borderRadius: 9,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  parentOptionSelected: {
    backgroundColor: '#29262D',
    borderColor: '#29262D',
  },
  parentOptionText: {
    color: '#5E5862',
    fontSize: 12,
    fontWeight: '600',
    maxWidth: 120,
  },
  parentOptionTextSelected: {
    color: '#FFFFFF',
  },
  input: {
    backgroundColor: '#FAF9F7',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#D8D2CC',
    color: '#29262D',
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
  },
  instructionsHeader: {
    marginBottom: 8,
  },
  instructionsTitle: {
    color: '#29262D',
    fontSize: 16,
    fontWeight: '700',
  },
  textArea: {
    backgroundColor: '#FAF9F7',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D8D2CC',
    color: '#29262D',
    padding: 14,
    fontSize: 14,
    lineHeight: 20,
    minHeight: 160,
    marginBottom: 16,
  },
  aiButtonRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  magicButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: '#FF9B8E',
    gap: 6,
  },
  magicButtonText: {
    color: '#B9502E',
    fontSize: 13,
    fontWeight: '600',
  },
  magicSecondaryButton: {
    borderColor: '#D8D2CC',
  },
  magicSecondaryText: {
    color: '#29262D',
    fontSize: 13,
    fontWeight: '600',
  },
  voiceEditButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#D8D2CC',
    gap: 6,
  },
  voiceEditText: {
    color: '#5E5862',
    fontSize: 13,
    fontWeight: '600',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF6D5A',
    borderRadius: 12,
    paddingVertical: 16,
    gap: 8,
  },
  saveDock: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 8,
    backgroundColor: '#F7F5F2',
    borderTopWidth: 1,
    borderTopColor: '#E3DEDA',
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(41, 38, 45, 0.45)',
    justifyContent: 'flex-end',
  },
  voiceModalCard: {
    backgroundColor: '#F7F5F2',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    borderWidth: 1,
    borderColor: '#DDD8D3',
  },
  modalCard: {
    backgroundColor: '#F7F5F2',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    borderWidth: 1,
    borderColor: '#DDD8D3',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  modalTitle: {
    color: '#29262D',
    fontSize: 18,
    fontWeight: '700',
  },
  modalSub: {
    color: '#756F79',
    fontSize: 13,
    marginBottom: 16,
    lineHeight: 18,
  },
  modalInput: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D8D2CC',
    color: '#29262D',
    padding: 12,
    fontSize: 15,
    minHeight: 80,
    textAlignVertical: 'top',
    marginBottom: 16,
  },
  modalSubmitButton: {
    backgroundColor: '#FF6D5A',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  modalSubmitText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
});
