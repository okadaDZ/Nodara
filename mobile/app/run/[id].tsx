import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
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
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { StatusBar } from 'expo-status-bar';
import { api } from '@/services/api';
import { Workflow, WorkflowRun } from '@/types/workflow';
import { RunStatus } from '@/components/RunStatus';
import { Check, Copy, Play, RotateCcw, Share2, Sparkles } from 'lucide-react-native';

export default function RunWorkflowScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [promptInput, setPromptInput] = useState('');
  const [loadingWf, setLoadingWf] = useState(true);
  const [startingRun, setStartingRun] = useState(false);
  const [currentRun, setCurrentRun] = useState<WorkflowRun | null>(null);
  const [copied, setCopied] = useState(false);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadWorkflow = useCallback(async () => {
    if (!id) return;
    try {
      setLoadingWf(true);
      const wf = await api.getWorkflow(id);
      setWorkflow(wf);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Could not load workflow');
    } finally {
      setLoadingWf(false);
    }
  }, [id]);

  useEffect(() => {
    loadWorkflow();
  }, [loadWorkflow]);

  // Clean up polling interval
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const startPolling = (runId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const updatedRun = await api.getRunStatus(runId);
        setCurrentRun(updatedRun);

        if (updatedRun.status === 'completed' || updatedRun.status === 'failed') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (err) {
        console.warn('Poll error:', err);
      }
    }, 1000);
  };

  const handleStartRun = async () => {
    if (!id || !promptInput.trim()) {
      Alert.alert('Required', 'Please enter an input prompt for the workflow.');
      return;
    }

    try {
      setStartingRun(true);
      const run = await api.runWorkflow(id, promptInput.trim());
      setCurrentRun(run);
      startPolling(run.id);
    } catch (err: any) {
      Alert.alert('Execution Error', err.message || 'Could not initiate workflow run.');
    } finally {
      setStartingRun(false);
    }
  };

  const handleCopy = () => {
    if (!currentRun?.final_output) return;
    Clipboard.setStringAsync(currentRun.final_output).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const enableWorkflow = async () => {
    if (!workflow) return;
    try {
      const enabled = await api.setWorkflowEnabled(workflow.id, true);
      setWorkflow(enabled);
    } catch (err: any) {
      Alert.alert('Could not turn on workflow', err.message || 'Try again.');
    }
  };

  const handleShare = async () => {
    if (!currentRun?.final_output) return;
    try {
      await Share.share({
        message: currentRun.final_output,
        title: `${workflow?.name || 'Agent Workflow'} Result`,
      });
    } catch (err) {
      console.warn('Share error:', err);
    }
  };

  const handleRunAgain = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setCurrentRun(null);
  };

  if (loadingWf) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FF6D5A" />
        <Text style={styles.loadingText}>Preparing workflow…</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <Text style={styles.title}>{workflow?.name || 'Run Workflow'}</Text>
          <Text style={styles.subtitle}>
            {workflow?.nodes.length || 0} nodes · parallel branches and routing handled automatically
          </Text>

          {!currentRun ? (
            <View>
              {workflow && !workflow.enabled ? (
                <View style={styles.offNotice}>
                  <View style={styles.offNoticeCopy}>
                    <Text style={styles.offNoticeTitle}>This workflow is off</Text>
                    <Text style={styles.offNoticeText}>Turn it on to start a new run.</Text>
                  </View>
                  <TouchableOpacity style={styles.enableButton} onPress={enableWorkflow}>
                    <Text style={styles.enableButtonText}>Turn on</Text>
                  </TouchableOpacity>
                </View>
              ) : null}

              <View style={styles.inputCard}>
              <Text style={styles.inputLabel}>Starting input</Text>
              <Text style={styles.inputHelp}>Give the first agents the context they need. The result will flow through the graph.</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Example: Research this market and build a launch recommendation…"
                placeholderTextColor="#A59FA8"
                multiline
                numberOfLines={4}
                value={promptInput}
                onChangeText={setPromptInput}
                textAlignVertical="top"
              />

              <TouchableOpacity
                activeOpacity={0.8}
                style={[styles.runButton, (!promptInput.trim() || !workflow?.enabled) && styles.disabledButton]}
                onPress={handleStartRun}
                disabled={!promptInput.trim() || startingRun || !workflow?.enabled}
              >
                {startingRun ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Play size={18} color="#FFFFFF" fill="#FFFFFF" />
                    <Text style={styles.runButtonText}>Run workflow</Text>
                  </>
                )}
              </TouchableOpacity>
              </View>
            </View>
          ) : (
            <View>
              <RunStatus run={currentRun} />

              {currentRun.status === 'completed' && currentRun.final_output && (
                <View style={styles.resultCard}>
                  <View style={styles.resultHeader}>
                    <Sparkles size={20} color="#B9502E" />
                    <Text style={styles.resultTitle}>Final output</Text>
                  </View>

                  <Text style={styles.resultText}>{currentRun.final_output}</Text>

                  <View style={styles.resultActions}>
                    <TouchableOpacity style={styles.actionBtn} onPress={handleCopy}>
                      {copied ? <Check size={16} color="#B9502E" /> : <Copy size={16} color="#B9502E" />}
                      <Text style={styles.actionBtnText}>{copied ? 'Copied' : 'Copy'}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.actionBtn} onPress={handleShare}>
                      <Share2 size={16} color="#B9502E" />
                      <Text style={styles.actionBtnText}>Share</Text>
                    </TouchableOpacity>

                    <TouchableOpacity style={styles.actionBtn} onPress={handleRunAgain}>
                      <RotateCcw size={16} color="#756F79" />
                      <Text style={[styles.actionBtnText, { color: '#756F79' }]}>Run again</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}

              {currentRun.status === 'failed' && (
                <View style={styles.errorCard}>
                  <Text style={styles.errorTitle}>Run stopped</Text>
                  <Text style={styles.errorDescription}>
                    {currentRun.error || 'One of the agents could not complete its task.'}
                  </Text>
                  <TouchableOpacity style={styles.retryButton} onPress={handleRunAgain}>
                    <RotateCcw size={16} color="#FFFFFF" />
                    <Text style={styles.retryButtonText}>Try again</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}
        </ScrollView>
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
    paddingBottom: 48,
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
    lineHeight: 20,
    marginBottom: 24,
  },
  offNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF0ED',
    borderWidth: 1,
    borderColor: '#FFC8BF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
  },
  offNoticeCopy: { flex: 1 },
  offNoticeTitle: { color: '#29262D', fontSize: 14, fontWeight: '800' },
  offNoticeText: { color: '#756F79', fontSize: 12, marginTop: 2 },
  enableButton: { minHeight: 44, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#FF9B8E', borderRadius: 9, paddingHorizontal: 13, alignItems: 'center', justifyContent: 'center' },
  enableButtonText: { color: '#B9502E', fontSize: 12, fontWeight: '800' },
  inputCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#DDD8D3',
  },
  inputLabel: {
    color: '#29262D',
    fontSize: 15,
    fontWeight: '800',
    marginBottom: 4,
  },
  inputHelp: { color: '#756F79', fontSize: 12, lineHeight: 17, marginBottom: 12 },
  textInput: {
    backgroundColor: '#FAF9F7',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D8D2CC',
    color: '#29262D',
    padding: 14,
    fontSize: 15,
    minHeight: 100,
    marginBottom: 16,
  },
  runButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF6D5A',
    borderRadius: 12,
    minHeight: 52,
    gap: 8,
  },
  disabledButton: {
    backgroundColor: '#CFC9C4',
  },
  runButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  resultCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    marginTop: 16,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#EEEAE7',
  },
  resultTitle: {
    color: '#29262D',
    fontSize: 16,
    fontWeight: '700',
  },
  resultText: {
    color: '#3F3A42',
    fontSize: 14,
    lineHeight: 22,
    marginBottom: 16,
  },
  resultActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    flexWrap: 'wrap',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#EEEAE7',
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF9F7',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    gap: 6,
    minHeight: 44,
  },
  actionBtnText: {
    color: '#B9502E',
    fontSize: 13,
    fontWeight: '600',
  },
  errorCard: {
    backgroundColor: '#FFF7F5',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E7A59C',
    marginTop: 16,
  },
  errorTitle: {
    color: '#A63F36',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 6,
  },
  errorDescription: {
    color: '#6D514E',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C94D43',
    borderRadius: 10,
    paddingVertical: 12,
    gap: 6,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
});
