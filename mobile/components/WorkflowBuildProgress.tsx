import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Check, Workflow } from 'lucide-react-native';
import { ImageWorkflowStage } from '@/types/workflow';

const STEPS: { stage: ImageWorkflowStage; label: string; detail: string }[] = [
  { stage: 'queued', label: 'Preparing image', detail: 'Uploading the full-resolution sketch' },
  { stage: 'validate_image', label: 'Checking the diagram', detail: 'Looking for boxes, labels, and arrows' },
  { stage: 'read_diagram', label: 'Reading the sketch', detail: 'Identifying every visible workflow element' },
  { stage: 'build_graph', label: 'Building the graph', detail: 'Connecting nodes, branches, and parallel paths' },
  { stage: 'review_structure', label: 'Reviewing structure', detail: 'Checking the extracted graph against the image' },
  { stage: 'validate_logic', label: 'Validating logic', detail: 'Finding gaps, loops, and ambiguous routes' },
  { stage: 'write_prompts', label: 'Writing agent prompts', detail: 'Creating instructions for each executable node' },
  { stage: 'review_prompts', label: 'Reviewing collaboration', detail: 'Checking how agent outputs flow downstream' },
  { stage: 'enhance_prompts', label: 'Refining instructions', detail: 'Applying improvements agent by agent' },
  { stage: 'finalize_workflow', label: 'Saving your workflow', detail: 'Assembling the editable canvas' },
];

const STAGE_INDEX: Record<ImageWorkflowStage, number> = {
  queued: 0,
  validate_image: 1,
  read_diagram: 2,
  build_graph: 3,
  review_structure: 4,
  validate_logic: 5,
  write_prompts: 6,
  review_prompts: 7,
  enhance_prompts: 8,
  finalize_workflow: 9,
  complete: 10,
};

export function WorkflowBuildProgress({ visible, stage }: { visible: boolean; stage: ImageWorkflowStage }) {
  const pulse = useRef(new Animated.Value(0.45)).current;
  const [reduceMotion, setReduceMotion] = useState(false);
  const currentIndex = STAGE_INDEX[stage];

  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    if (!visible || reduceMotion) {
      pulse.stopAnimation();
      pulse.setValue(1);
      return;
    }
    const animation = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 650, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 0.45, duration: 650, easing: Easing.in(Easing.cubic), useNativeDriver: true }),
    ]));
    animation.start();
    return () => animation.stop();
  }, [pulse, reduceMotion, visible]);

  if (!visible) return null;
  const active = STEPS[Math.min(currentIndex, STEPS.length - 1)];

  return (
    <View style={styles.backdrop} accessibilityViewIsModal>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.sheet} accessibilityRole="progressbar" accessibilityLabel={`${active.label}. ${active.detail}`}>
          <View style={styles.header}>
            <View style={styles.headerIcon}><Workflow size={21} color="#FF6D5A" /></View>
            <View style={styles.headerCopy}>
              <Text style={styles.title}>Building your workflow</Text>
              <Text style={styles.headerStatus}>The agents are working through your sketch</Text>
            </View>
            <Text style={styles.progressCount}>Step {Math.min(currentIndex + 1, 10)} of 10</Text>
          </View>

          <View style={styles.progressRail}>
            <View style={[styles.progressFill, { width: `${Math.min(currentIndex + 1, 10) * 10}%` }]} />
          </View>

          <View style={styles.activeStage}>
            <Animated.View style={[styles.activeHalo, { opacity: pulse }]}>
              <View style={styles.activeDot} />
            </Animated.View>
            <View style={styles.activeCopy}>
              <Text style={styles.activeContext}>Working now</Text>
              <Text style={styles.activeLabel} accessibilityLiveRegion="polite">{active.label}</Text>
              <Text style={styles.activeDetail}>{active.detail}</Text>
            </View>
          </View>

          {currentIndex > 0 ? (
            <View style={styles.stageGroup}>
              <Text style={styles.groupLabel}>Completed</Text>
              {STEPS.slice(0, currentIndex).map((item) => (
                <View key={item.stage} style={styles.compactRow}>
                  <View style={styles.completeDot}><Check size={10} strokeWidth={3} color="#FFFFFF" /></View>
                  <Text style={styles.completeLabel}>{item.label}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {currentIndex < STEPS.length - 1 ? (
            <View style={styles.stageGroup}>
              <Text style={styles.groupLabel}>Up next</Text>
              {STEPS.slice(currentIndex + 1).map((item) => (
                <View key={item.stage} style={styles.compactRow}>
                  <View style={styles.waitingDot} />
                  <Text style={styles.waitingLabel}>{item.label}</Text>
                </View>
              ))}
            </View>
          ) : null}

          <Text style={styles.footer}>This screen updates automatically as each agent finishes.</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFillObject, zIndex: 9999, elevation: 9999, backgroundColor: '#F7F5F2' },
  scrollContent: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 32 },
  sheet: { width: '100%', maxWidth: 430, alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center' },
  headerIcon: { width: 44, height: 44, borderRadius: 13, backgroundColor: '#FFF0ED', alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  headerCopy: { flex: 1 },
  title: { color: '#29262D', fontSize: 20, fontWeight: '800', letterSpacing: -0.45 },
  headerStatus: { color: '#756F79', fontSize: 11, lineHeight: 15, marginTop: 3 },
  progressCount: { color: '#756F79', fontSize: 11, fontWeight: '700', fontVariant: ['tabular-nums'], marginLeft: 8 },
  progressRail: { height: 5, marginTop: 20, borderRadius: 3, overflow: 'hidden', backgroundColor: '#E5E0DB' },
  progressFill: { height: '100%', borderRadius: 3, backgroundColor: '#FF6D5A' },
  activeStage: { minHeight: 94, marginTop: 20, paddingHorizontal: 16, paddingVertical: 15, borderRadius: 14, backgroundColor: '#FFF0ED', flexDirection: 'row', alignItems: 'center' },
  activeHalo: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#FFC8C0', alignItems: 'center', justifyContent: 'center', marginRight: 13 },
  activeDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#FF6D5A' },
  activeCopy: { flex: 1 },
  activeContext: { color: '#B9502E', fontSize: 10, lineHeight: 13, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6 },
  activeLabel: { color: '#29262D', fontSize: 17, lineHeight: 21, fontWeight: '800', marginTop: 2 },
  activeDetail: { color: '#756F79', fontSize: 12, lineHeight: 17, marginTop: 3 },
  stageGroup: { marginTop: 20 },
  groupLabel: { color: '#756F79', fontSize: 11, fontWeight: '800', marginBottom: 7 },
  compactRow: { minHeight: 32, flexDirection: 'row', alignItems: 'center' },
  completeDot: { width: 17, height: 17, borderRadius: 9, backgroundColor: '#FF6D5A', alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  completeLabel: { color: '#4A454D', fontSize: 13, fontWeight: '600' },
  waitingDot: { width: 13, height: 13, borderRadius: 7, borderWidth: 2, borderColor: '#CFC8C2', marginLeft: 2, marginRight: 12 },
  waitingLabel: { color: '#9A949D', fontSize: 13, fontWeight: '600' },
  footer: { color: '#756F79', fontSize: 11, lineHeight: 16, textAlign: 'center', marginTop: 22, paddingTop: 16, borderTopWidth: 1, borderTopColor: '#DDD8D3' },
});
