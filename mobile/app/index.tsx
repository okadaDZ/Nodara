import React, { PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  LayoutAnimation,
  PanResponder,
  Platform,
  RefreshControl,
  SafeAreaView,
  SectionList,
  Share,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  UIManager,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { api } from '@/services/api';
import { WorkflowSummary } from '@/types/workflow';
import { ArrowRight, CalendarClock, Camera, Check, ChevronDown, Download, GitBranch, History, Pencil, PlayCircle, Settings, Trash2, X } from 'lucide-react-native';

const COLORS = {
  canvas: '#F7F5F2',
  surface: '#FFFFFF',
  ink: '#29262D',
  muted: '#756F79',
  line: '#DDD8D3',
  coral: '#FF6D5A',
  coralSoft: '#FFF0ED',
};

const SWIPE_ACTION_WIDTH = 92;
type SwipeDirection = -1 | 0 | 1;

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

type WorkflowDateSection = {
  title: string;
  data: WorkflowSummary[];
};

function parseWorkflowDate(value?: string): Date | null {
  if (!value) return null;
  const includesTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value);
  const parsed = new Date(includesTimezone ? value : `${value}Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function localCalendarDay(date: Date): number {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
}

export function groupWorkflowsByDate(
  workflows: WorkflowSummary[],
  now = new Date(),
): WorkflowDateSection[] {
  const today = localCalendarDay(now);
  const dayMs = 24 * 60 * 60 * 1000;
  const ordered = [...workflows].sort((left, right) => {
    const leftDate = parseWorkflowDate(left.updated_at || left.created_at)?.getTime() ?? 0;
    const rightDate = parseWorkflowDate(right.updated_at || right.created_at)?.getTime() ?? 0;
    return rightDate - leftDate;
  });
  const grouped = new Map<string, WorkflowSummary[]>();

  for (const workflow of ordered) {
    const date = parseWorkflowDate(workflow.updated_at || workflow.created_at);
    let title = 'Older';
    if (date) {
      const daysAgo = Math.round((today - localCalendarDay(date)) / dayMs);
      if (daysAgo <= 0) title = 'Today';
      else if (daysAgo === 1) title = 'Yesterday';
      else if (daysAgo <= 7) title = 'Previous 7 Days';
      else if (daysAgo <= 30) title = 'Previous 30 Days';
      else {
        title = date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
      }
    }
    grouped.set(title, [...(grouped.get(title) ?? []), workflow]);
  }

  return Array.from(grouped, ([title, data]) => ({ title, data }));
}

function SwipeActionCard({
  name,
  onOpen,
  onDelete,
  onExport,
  locked = false,
  children,
}: PropsWithChildren<{
  name: string;
  onOpen: () => void;
  onDelete: () => Promise<void>;
  onExport: () => Promise<void>;
  locked?: boolean;
}>) {
  const translateX = useRef(new Animated.Value(0)).current;
  const openRef = useRef<SwipeDirection>(0);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const settle = useCallback((direction: SwipeDirection) => {
    openRef.current = direction;
    Animated.spring(translateX, {
      toValue: direction * SWIPE_ACTION_WIDTH,
      useNativeDriver: true,
      speed: 24,
      bounciness: 0,
    }).start();
  }, [translateX]);

  const panResponder = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, gesture) =>
      Math.abs(gesture.dx) > 8 && Math.abs(gesture.dx) > Math.abs(gesture.dy) * 1.25,
    onPanResponderMove: (_, gesture) => {
      const origin = openRef.current * SWIPE_ACTION_WIDTH;
      translateX.setValue(Math.max(-SWIPE_ACTION_WIDTH, Math.min(SWIPE_ACTION_WIDTH, origin + gesture.dx)));
    },
    onPanResponderRelease: (_, gesture) => {
      const projected = openRef.current * SWIPE_ACTION_WIDTH + gesture.dx;
      if (projected < -SWIPE_ACTION_WIDTH * 0.42 || gesture.vx < -0.45) settle(-1);
      else if (projected > SWIPE_ACTION_WIDTH * 0.42 || gesture.vx > 0.45) settle(1);
      else settle(0);
    },
    onPanResponderTerminate: () => settle(openRef.current),
  })).current;

  const confirmDelete = () => {
    Alert.alert(
      'Delete workflow?',
      `“${name}” and its saved configuration will be permanently deleted.`,
      [
        { text: 'Cancel', style: 'cancel', onPress: () => settle(0) },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              setDeleting(true);
              await onDelete();
            } catch {
              setDeleting(false);
              settle(0);
            }
          },
        },
      ],
    );
  };

  const exportToN8n = async () => {
    try {
      setExporting(true);
      await onExport();
      settle(0);
    } catch {
      settle(0);
    } finally {
      setExporting(false);
    }
  };

  return (
    <View style={styles.swipeContainer}>
      <TouchableOpacity
        activeOpacity={0.82}
        style={styles.exportAction}
        onPress={exportToN8n}
        disabled={exporting}
        accessibilityRole="button"
        accessibilityLabel={`Export ${name} to n8n`}
      >
        {exporting ? <ActivityIndicator color="#FFFFFF" /> : <Download size={21} color="#FFFFFF" />}
        <Text style={styles.swipeActionText}>{exporting ? 'Exporting' : 'n8n'}</Text>
      </TouchableOpacity>
      <TouchableOpacity
        activeOpacity={0.82}
        style={styles.deleteAction}
        onPress={confirmDelete}
        disabled={deleting}
        accessibilityRole="button"
        accessibilityLabel={`Delete ${name}`}
      >
        {deleting ? <ActivityIndicator color="#FFFFFF" /> : <Trash2 size={21} color="#FFFFFF" />}
        <Text style={styles.swipeActionText}>{deleting ? 'Deleting' : 'Delete'}</Text>
      </TouchableOpacity>
      <Animated.View style={{ transform: [{ translateX }] }} {...(locked ? {} : panResponder.panHandlers)}>
        {locked ? (
          <View style={styles.workflowCard}>{children}</View>
        ) : (
          <TouchableOpacity activeOpacity={0.75} style={styles.workflowCard} onPress={() => openRef.current ? settle(0) : onOpen()}>
            {children}
          </TouchableOpacity>
        )}
      </Animated.View>
    </View>
  );
}

export default function HomeScreen() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [openingDemo, setOpeningDemo] = useState(false);
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [renamingWorkflowId, setRenamingWorkflowId] = useState<string | null>(null);
  const [workflowsExpanded, setWorkflowsExpanded] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const workflowsReveal = useRef(new Animated.Value(0)).current;
  const workflowSections = useMemo(() => groupWorkflowsByDate(workflows), [workflows]);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) setReduceMotion(enabled);
    });
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  const fetchWorkflows = useCallback(async () => {
    try {
      setWorkflows(await api.listWorkflows());
    } catch (err: any) {
      console.warn('Could not load workflows:', err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { fetchWorkflows(); }, [fetchWorkflows]));

  const deleteWorkflow = useCallback(async (workflow: WorkflowSummary) => {
    try {
      const deleted = await api.deleteWorkflow(workflow.id);
      if (!deleted) throw new Error('The server did not delete this workflow.');
      setWorkflows((current) => current.filter((item) => item.id !== workflow.id));
    } catch (err: any) {
      Alert.alert('Delete Failed', err.message || 'Could not delete this workflow.');
      throw err;
    }
  }, []);

  const exportWorkflow = useCallback(async (workflow: WorkflowSummary) => {
    try {
      const json = await api.exportToN8n(workflow.id);
      await Share.share({ message: json, title: `${workflow.name} — n8n export` });
    } catch (err: any) {
      Alert.alert('Export Failed', err.message || 'Could not export this workflow to n8n.');
      throw err;
    }
  }, []);

  const toggleWorkflow = useCallback(async (workflow: WorkflowSummary, enabled: boolean) => {
    setWorkflows((current) => current.map((item) =>
      item.id === workflow.id ? { ...item, enabled } : item
    ));
    try {
      await api.setWorkflowEnabled(workflow.id, enabled);
    } catch (err: any) {
      setWorkflows((current) => current.map((item) =>
        item.id === workflow.id ? { ...item, enabled: workflow.enabled } : item
      ));
      Alert.alert('Could not update workflow', err.message || 'Try again.');
    }
  }, []);

  const startRename = useCallback((workflow: WorkflowSummary) => {
    setEditingWorkflowId(workflow.id);
    setRenameDraft(workflow.name);
  }, []);

  const cancelRename = useCallback(() => {
    if (renamingWorkflowId) return;
    setEditingWorkflowId(null);
    setRenameDraft('');
  }, [renamingWorkflowId]);

  const saveRename = useCallback(async (workflow: WorkflowSummary) => {
    const name = renameDraft.trim();
    if (!name) {
      Alert.alert('Name required', 'Enter a name for this workflow.');
      return;
    }
    if (name === workflow.name) {
      cancelRename();
      return;
    }
    try {
      setRenamingWorkflowId(workflow.id);
      const updated = await api.renameWorkflow(workflow.id, name);
      setWorkflows((current) => current.map((item) =>
        item.id === workflow.id ? { ...item, name: updated.name, updated_at: new Date().toISOString() } : item
      ));
      setEditingWorkflowId(null);
      setRenameDraft('');
    } catch (err: any) {
      Alert.alert('Could not rename workflow', err.message || 'Check your connection and try again.');
    } finally {
      setRenamingWorkflowId(null);
    }
  }, [cancelRename, renameDraft]);

  const toggleWorkflowTray = useCallback(() => {
    const nextExpanded = !workflowsExpanded;
    if (!reduceMotion) {
      LayoutAnimation.configureNext({
        duration: 220,
        create: { type: LayoutAnimation.Types.easeInEaseOut, property: LayoutAnimation.Properties.opacity },
        update: { type: LayoutAnimation.Types.easeInEaseOut },
        delete: { type: LayoutAnimation.Types.easeInEaseOut, property: LayoutAnimation.Properties.opacity },
      });
    }
    setWorkflowsExpanded(nextExpanded);
    Animated.timing(workflowsReveal, {
      toValue: nextExpanded ? 1 : 0,
      duration: reduceMotion ? 0 : 220,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [reduceMotion, workflowsExpanded, workflowsReveal]);

  const scheduleLabel = (workflow: WorkflowSummary) => {
    if (!workflow.schedule_enabled || !workflow.next_run_at) return 'Schedule';
    const next = new Date(workflow.next_run_at);
    if (Number.isNaN(next.getTime())) return 'Scheduled';
    return next.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };

  const lastRunLabel = (workflow: WorkflowSummary) => {
    if (!workflow.run_count || !workflow.last_run_at) return 'No runs yet';
    const date = new Date(workflow.last_run_at);
    if (Number.isNaN(date.getTime())) return `${workflow.run_count} ${workflow.run_count === 1 ? 'run' : 'runs'}`;
    return `${workflow.run_count} ${workflow.run_count === 1 ? 'run' : 'runs'} · Last ${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
  };

  const openDemoWorkflow = async () => {
    try {
      setOpeningDemo(true);
      const workflow = await api.getDemoWorkflow();
      router.push(`/workflow/${workflow.id}`);
    } catch (err: any) {
      Alert.alert('Demo unavailable', err.message || 'Could not open the demo workflow.');
    } finally {
      setOpeningDemo(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <SectionList
        sections={workflowsExpanded ? workflowSections : []}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => {
            setRefreshing(true);
            fetchWorkflows();
          }} tintColor={COLORS.coral} />
        }
        showsVerticalScrollIndicator={false}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <View>
            <View style={styles.brandRow}>
              <View style={styles.brandMark}>
                <View style={styles.brandLine} />
                <View style={[styles.brandPoint, styles.brandPointLeft]} />
                <View style={[styles.brandPoint, styles.brandPointCenter]} />
                <View style={[styles.brandPoint, styles.brandPointRight]} />
              </View>
              <Text style={styles.brandName}>nodara</Text>
              <TouchableOpacity style={styles.settingsButton} onPress={() => router.push('/settings')} accessibilityLabel="Open settings">
                <Settings size={19} color={COLORS.ink} />
              </TouchableOpacity>
              <View style={styles.flowCount}>
                <GitBranch size={12} color={COLORS.muted} />
                <Text style={styles.flowCountText}>{workflows.length}</Text>
              </View>
            </View>

            <View style={styles.hero}>
              <Text style={styles.heroTitle}>Turn a sketch into an agent workflow.</Text>
              <Text style={styles.heroCopy}>
                Photograph boxes and arrows, then edit and run the result.
              </Text>

              <TouchableOpacity
                activeOpacity={0.88}
                style={styles.primaryButton}
                onPress={() => router.push('/create/photo')}
                accessibilityRole="button"
                accessibilityLabel="Scan a workflow"
                accessibilityHint="Opens the camera or photo library"
              >
                <View style={styles.primaryIcon}>
                  <Camera size={26} strokeWidth={2.2} color={COLORS.coral} />
                </View>
                <View style={styles.primaryTextBlock}>
                  <Text style={styles.primaryTitle}>Scan a workflow</Text>
                  <Text style={styles.primarySubtitle}>Photograph a sketch or choose one from your library</Text>
                </View>
                <View style={styles.primaryArrow}>
                  <ArrowRight size={22} color="#FFFFFF" />
                </View>
              </TouchableOpacity>

              <View style={styles.discoveryRow}>
                <TouchableOpacity
                  style={styles.discoveryAction}
                  onPress={() => router.push('/how-it-works')}
                  accessibilityRole="button"
                  accessibilityLabel="Show me how Nodara works"
                >
                  <PlayCircle size={18} color={COLORS.coral} />
                  <Text style={styles.discoveryText}>Show me how it works</Text>
                </TouchableOpacity>
                <View style={styles.discoveryDivider} />
                <TouchableOpacity
                  style={styles.discoveryAction}
                  onPress={openDemoWorkflow}
                  disabled={openingDemo}
                  accessibilityRole="button"
                  accessibilityLabel="Open the demo workflow"
                >
                  {openingDemo
                    ? <ActivityIndicator size="small" color={COLORS.coral} />
                    : <GitBranch size={18} color={COLORS.coral} />}
                  <Text style={styles.discoveryText}>Show demo</Text>
                </TouchableOpacity>
              </View>
            </View>

            <TouchableOpacity
              activeOpacity={0.78}
              style={[styles.workflowTray, workflowsExpanded && styles.workflowTrayExpanded]}
              onPress={toggleWorkflowTray}
              accessibilityRole="button"
              accessibilityState={{ expanded: workflowsExpanded }}
              accessibilityLabel={`${workflowsExpanded ? 'Collapse' : 'Expand'} your workflows, ${workflows.length} saved`}
            >
              <View style={styles.workflowTrayIcon}>
                <GitBranch size={17} color={COLORS.coral} />
              </View>
              <View style={styles.workflowTrayCopy}>
                <Text style={styles.sectionTitle}>Your workflows</Text>
                <Text style={styles.workflowTrayHint}>
                  {workflowsExpanded ? 'Tap to make room' : 'Tap to browse saved workflows'}
                </Text>
              </View>
              <Text style={styles.sectionCount}>{workflows.length}</Text>
              <Animated.View style={{
                transform: [{
                  rotate: workflowsReveal.interpolate({
                    inputRange: [0, 1],
                    outputRange: ['0deg', '180deg'],
                  }),
                }],
              }}>
                <ChevronDown size={19} color={COLORS.muted} />
              </Animated.View>
            </TouchableOpacity>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.dateHeading}>
            <Text style={styles.dateHeadingText}>{section.title}</Text>
          </View>
        )}
        renderItem={({ item }) => (
          <SwipeActionCard
            name={item.name}
            onOpen={() => router.push(`/workflow/${item.id}`)}
            onDelete={() => deleteWorkflow(item)}
            onExport={() => exportWorkflow(item)}
            locked={editingWorkflowId === item.id}
          >
            <View style={styles.workflowTopRow}>
              <View style={[styles.workflowIcon, styles.coralIcon]}>
                <GitBranch size={18} color={COLORS.coral} />
              </View>
              <View style={styles.workflowCopy}>
                {editingWorkflowId === item.id ? (
                  <View style={styles.renameRow}>
                    <TextInput
                      autoFocus
                      value={renameDraft}
                      onChangeText={setRenameDraft}
                      onSubmitEditing={() => saveRename(item)}
                      returnKeyType="done"
                      selectTextOnFocus
                      maxLength={120}
                      editable={renamingWorkflowId !== item.id}
                      style={styles.renameInput}
                      accessibilityLabel="Workflow name"
                    />
                    <TouchableOpacity
                      style={styles.renameAction}
                      onPress={cancelRename}
                      disabled={renamingWorkflowId === item.id}
                      accessibilityRole="button"
                      accessibilityLabel="Cancel renaming"
                    >
                      <X size={17} color={COLORS.muted} />
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.renameAction, styles.renameConfirm]}
                      onPress={() => saveRename(item)}
                      disabled={renamingWorkflowId === item.id}
                      accessibilityRole="button"
                      accessibilityLabel="Save workflow name"
                    >
                      {renamingWorkflowId === item.id
                        ? <ActivityIndicator size="small" color="#FFFFFF" />
                        : <Check size={17} color="#FFFFFF" />}
                    </TouchableOpacity>
                  </View>
                ) : (
                  <View style={styles.titleRow}>
                    <Text style={styles.workflowTitle} numberOfLines={1}>{item.name}</Text>
                    <TouchableOpacity
                      style={styles.renameButton}
                      onPress={() => startRename(item)}
                      accessibilityRole="button"
                      accessibilityLabel={`Rename ${item.name}`}
                    >
                      <Pencil size={14} color={COLORS.muted} />
                    </TouchableOpacity>
                  </View>
                )}
                <Text style={styles.workflowDescription} numberOfLines={1}>
                  {item.description || 'Editable agent workflow'}
                </Text>
              </View>
              <ArrowRight size={18} color="#A59FA8" />
            </View>

            <View style={styles.workflowMeta}>
              <View style={styles.miniFlow}>
                {Array.from({ length: Math.min(item.node_count, 4) }, (_, nodeIndex) => (
                  <React.Fragment key={nodeIndex}>
                    {nodeIndex > 0 ? <View style={styles.miniLine} /> : null}
                    <View style={styles.miniNode} />
                  </React.Fragment>
                ))}
              </View>
              <Text style={styles.nodeCount}>{item.node_count} {item.node_count === 1 ? 'node' : 'nodes'}</Text>
              <View style={styles.enabledControl}>
                <Text style={[styles.enabledLabel, !item.enabled && styles.disabledLabel]}>{item.enabled ? 'On' : 'Off'}</Text>
                <Switch
                  value={item.enabled}
                  onValueChange={(enabled) => toggleWorkflow(item, enabled)}
                  trackColor={{ false: '#D8D2CC', true: '#FF9B8E' }}
                  thumbColor={item.enabled ? COLORS.coral : '#FFFFFF'}
                  ios_backgroundColor="#D8D2CC"
                  accessibilityLabel={`${item.enabled ? 'Disable' : 'Enable'} ${item.name}`}
                />
              </View>
            </View>
            <View style={styles.runSummaryRow}>
              <History size={14} color={COLORS.muted} />
              <Text style={styles.runSummaryText}>{lastRunLabel(item)}</Text>
            </View>
            <TouchableOpacity
              style={[styles.scheduleButton, item.schedule_enabled && styles.scheduleButtonActive]}
              onPress={() => router.push(`/schedule/${item.id}`)}
              accessibilityRole="button"
              accessibilityLabel={`Schedule ${item.name}`}
            >
              <CalendarClock size={14} color={item.schedule_enabled ? '#B9502E' : COLORS.muted} />
              <Text style={[styles.scheduleText, item.schedule_enabled && styles.scheduleTextActive]} numberOfLines={1}>{scheduleLabel(item)}</Text>
              <ArrowRight size={14} color={item.schedule_enabled ? '#B9502E' : '#A59FA8'} />
            </TouchableOpacity>
          </SwipeActionCard>
        )}
        ListEmptyComponent={workflowsExpanded ? (
          loading ? (
            <View style={styles.emptyState}>
              <ActivityIndicator color={COLORS.coral} />
              <Text style={styles.emptyText}>Loading your flows…</Text>
            </View>
          ) : (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>Your canvas is clear</Text>
              <Text style={styles.emptyText}>Scan your first diagram to see it here.</Text>
            </View>
          )
        ) : null}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: COLORS.canvas },
  content: { paddingHorizontal: 20, paddingBottom: 48 },
  brandRow: { height: 72, flexDirection: 'row', alignItems: 'center' },
  brandMark: { width: 28, height: 22, marginRight: 9, justifyContent: 'center' },
  brandLine: { height: 2, width: 24, marginLeft: 2, backgroundColor: COLORS.coral, borderRadius: 1 },
  brandPoint: { position: 'absolute', width: 7, height: 7, borderRadius: 4, backgroundColor: COLORS.surface, borderWidth: 2, borderColor: COLORS.coral },
  brandPointLeft: { left: 0 },
  brandPointCenter: { left: 10 },
  brandPointRight: { right: 0 },
  brandName: { color: COLORS.ink, fontSize: 20, fontWeight: '800', letterSpacing: -0.6 },
  settingsButton: { marginLeft: 'auto', padding: 9 },
  flowCount: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 99, backgroundColor: '#ECE9E5' },
  flowCountText: { color: COLORS.muted, fontSize: 12, fontWeight: '700' },
  hero: { paddingTop: 28 },
  heroTitle: { color: COLORS.ink, fontSize: 32, lineHeight: 36, fontWeight: '800', letterSpacing: -1.1, maxWidth: 350 },
  heroCopy: { color: COLORS.muted, fontSize: 15, lineHeight: 23, marginTop: 12, maxWidth: 330 },
  primaryButton: { marginTop: 28, minHeight: 124, borderRadius: 16, backgroundColor: COLORS.coral, paddingHorizontal: 18, paddingVertical: 20, flexDirection: 'row', alignItems: 'center' },
  primaryIcon: { width: 66, height: 66, borderRadius: 16, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginRight: 16 },
  primaryTextBlock: { flex: 1, paddingRight: 8 },
  primaryTitle: { color: '#FFFFFF', fontSize: 20, lineHeight: 24, fontWeight: '800', letterSpacing: -0.35 },
  primarySubtitle: { color: '#FFE4DF', fontSize: 12, lineHeight: 17, marginTop: 5 },
  primaryArrow: { width: 32, height: 44, alignItems: 'flex-end', justifyContent: 'center' },
  discoveryRow: { minHeight: 56, marginTop: 12, flexDirection: 'row', alignItems: 'stretch' },
  discoveryAction: { flex: 1, minHeight: 52, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 },
  discoveryDivider: { width: 1, height: 22, alignSelf: 'center', backgroundColor: COLORS.line },
  discoveryText: { color: COLORS.ink, fontSize: 12, fontWeight: '700' },
  workflowTray: { minHeight: 70, marginTop: 32, paddingHorizontal: 13, borderRadius: 14, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.surface, flexDirection: 'row', alignItems: 'center' },
  workflowTrayExpanded: { borderColor: '#CEC7C1' },
  workflowTrayIcon: { width: 38, height: 38, marginRight: 11, borderRadius: 11, backgroundColor: COLORS.coralSoft, alignItems: 'center', justifyContent: 'center' },
  workflowTrayCopy: { flex: 1 },
  sectionTitle: { color: COLORS.ink, fontSize: 16, fontWeight: '800', letterSpacing: -0.25 },
  workflowTrayHint: { color: COLORS.muted, fontSize: 11, marginTop: 2 },
  sectionCount: { color: COLORS.muted, fontSize: 12, fontWeight: '700', marginRight: 8 },
  dateHeading: { minHeight: 38, paddingTop: 14, paddingBottom: 8, flexDirection: 'row', alignItems: 'center' },
  dateHeadingText: { color: COLORS.ink, fontSize: 13, fontWeight: '700' },
  swipeContainer: { marginBottom: 10, borderRadius: 17, overflow: 'hidden', backgroundColor: '#D94A43' },
  exportAction: { position: 'absolute', top: 0, left: 0, bottom: 0, width: SWIPE_ACTION_WIDTH, alignItems: 'center', justifyContent: 'center', gap: 5, backgroundColor: '#C85D32' },
  deleteAction: { position: 'absolute', top: 0, right: 0, bottom: 0, width: SWIPE_ACTION_WIDTH, alignItems: 'center', justifyContent: 'center', gap: 5, backgroundColor: '#D94A43' },
  swipeActionText: { color: '#FFFFFF', fontSize: 12, fontWeight: '800' },
  workflowCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 15, borderWidth: 1, borderColor: COLORS.line },
  workflowTopRow: { flexDirection: 'row', alignItems: 'center' },
  workflowIcon: { width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  coralIcon: { backgroundColor: COLORS.coralSoft },
  workflowCopy: { flex: 1, marginRight: 8 },
  titleRow: { minHeight: 32, flexDirection: 'row', alignItems: 'center' },
  workflowTitle: { flex: 1, color: COLORS.ink, fontSize: 15, fontWeight: '700' },
  renameButton: { width: 36, height: 36, marginVertical: -5, alignItems: 'center', justifyContent: 'center' },
  renameRow: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 6 },
  renameInput: { flex: 1, height: 40, borderRadius: 9, borderWidth: 1, borderColor: COLORS.coral, backgroundColor: '#FFFAF8', paddingHorizontal: 10, color: COLORS.ink, fontSize: 16, fontWeight: '700' },
  renameAction: { width: 40, height: 40, borderRadius: 9, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.surface, alignItems: 'center', justifyContent: 'center' },
  renameConfirm: { borderColor: COLORS.coral, backgroundColor: COLORS.coral },
  workflowDescription: { color: COLORS.muted, fontSize: 12, marginTop: 3 },
  workflowMeta: { marginTop: 13, paddingTop: 11, borderTopWidth: 1, borderTopColor: '#EEEAE7', flexDirection: 'row', alignItems: 'center' },
  miniFlow: { flexDirection: 'row', alignItems: 'center' },
  miniNode: { width: 9, height: 9, borderRadius: 3, borderWidth: 2, borderColor: COLORS.coral, backgroundColor: COLORS.surface },
  miniLine: { width: 13, height: 1, backgroundColor: '#C7C0C9' },
  nodeCount: { color: COLORS.muted, fontSize: 11, fontWeight: '600', marginLeft: 9 },
  runSummaryRow: { minHeight: 31, marginTop: 5, paddingHorizontal: 10, flexDirection: 'row', alignItems: 'center', gap: 6 },
  runSummaryText: { color: COLORS.muted, fontSize: 11, fontWeight: '600' },
  scheduleButton: { minHeight: 40, marginTop: 8, paddingHorizontal: 10, borderRadius: 9, flexDirection: 'row', alignItems: 'center', gap: 6 }, scheduleButtonActive: { backgroundColor: COLORS.coralSoft }, scheduleText: { color: COLORS.muted, fontSize: 11, fontWeight: '700', flex: 1 }, scheduleTextActive: { color: '#B9502E' },
  enabledControl: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 5 }, enabledLabel: { color: COLORS.coral, fontSize: 11, fontWeight: '800' }, disabledLabel: { color: COLORS.muted },
  emptyState: { alignItems: 'center', paddingVertical: 35, paddingHorizontal: 20 },
  emptyTitle: { color: COLORS.ink, fontSize: 16, fontWeight: '800', marginBottom: 5 },
  emptyText: { color: COLORS.muted, fontSize: 13, marginTop: 8, textAlign: 'center' },
});
