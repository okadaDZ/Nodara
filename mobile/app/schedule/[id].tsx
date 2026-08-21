import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, SafeAreaView, ScrollView,
  StyleSheet, Switch, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { CalendarClock, Check, Clock3, Repeat2, Trash2 } from 'lucide-react-native';

import { api } from '@/services/api';
import { Workflow, WorkflowSchedule } from '@/types/workflow';

const COLORS = {
  canvas: '#F7F5F2', surface: '#FFFFFF', ink: '#29262D', muted: '#756F79',
  line: '#DDD8D3', coral: '#FF6D5A', coralDark: '#B9502E', coralSoft: '#FFF0ED',
};

function tomorrowDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

function localParts(value?: string | null): { date: string; time: string } {
  if (!value) return { date: tomorrowDate(), time: '09:00' };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { date: tomorrowDate(), time: '09:00' };
  const pad = (part: number) => String(part).padStart(2, '0');
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
  };
}

function nextRunLabel(value?: string | null): string {
  if (!value) return 'No upcoming run';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'No upcoming run'
    : date.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export default function ScheduleWorkflowScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const timezone = useMemo(() => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC', []);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [existing, setExisting] = useState<WorkflowSchedule | null>(null);
  const [mode, setMode] = useState<'once' | 'window'>('once');
  const [enabled, setEnabled] = useState(true);
  const [inputText, setInputText] = useState('');
  const [runDate, setRunDate] = useState(tomorrowDate());
  const [runTime, setRunTime] = useState('09:00');
  const [windowStart, setWindowStart] = useState('09:00');
  const [windowEnd, setWindowEnd] = useState('17:00');
  const [interval, setIntervalValue] = useState('60');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [loadedWorkflow, schedule] = await Promise.all([
        api.getWorkflow(id), api.getWorkflowSchedule(id),
      ]);
      setWorkflow(loadedWorkflow);
      setExisting(schedule);
      if (schedule) {
        setMode(schedule.mode);
        setEnabled(schedule.enabled);
        setInputText(schedule.input_text);
        const parts = localParts(schedule.run_at);
        setRunDate(parts.date);
        setRunTime(parts.time);
        setWindowStart(schedule.window_start || '09:00');
        setWindowEnd(schedule.window_end || '17:00');
        setIntervalValue(String(schedule.interval_minutes || 60));
      }
    } catch (error: any) {
      Alert.alert('Could not load schedule', error.message || 'Try again.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!id || !inputText.trim()) {
      Alert.alert('Starting input required', 'Add the input this workflow should receive when it runs.');
      return;
    }
    const clockPattern = /^([01]\d|2[0-3]):[0-5]\d$/;
    if ((mode === 'once' && !/^\d{4}-\d{2}-\d{2}$/.test(runDate)) ||
        (mode === 'once' && !clockPattern.test(runTime)) ||
        (mode === 'window' && (!clockPattern.test(windowStart) || !clockPattern.test(windowEnd)))) {
      Alert.alert('Check the schedule', 'Use YYYY-MM-DD for the date and 24-hour HH:MM for times.');
      return;
    }
    const intervalMinutes = Number(interval);
    if (mode === 'window' && (!Number.isInteger(intervalMinutes) || intervalMinutes < 5 || intervalMinutes > 1440)) {
      Alert.alert('Check the interval', 'Choose a whole number from 5 to 1440 minutes.');
      return;
    }
    const localRun = mode === 'once' ? new Date(`${runDate}T${runTime}:00`) : null;
    if (localRun && Number.isNaN(localRun.getTime())) {
      Alert.alert('Check the date', 'Choose a valid date and time.');
      return;
    }
    try {
      setSaving(true);
      const saved = await api.saveWorkflowSchedule(id, {
        mode,
        enabled,
        input_text: inputText.trim(),
        timezone,
        run_at: localRun?.toISOString() || null,
        window_start: mode === 'window' ? windowStart : null,
        window_end: mode === 'window' ? windowEnd : null,
        interval_minutes: mode === 'window' ? intervalMinutes : null,
      });
      setExisting(saved);
      Alert.alert('Schedule saved', `Next run: ${nextRunLabel(saved.next_run_at)}`, [
        { text: 'Done', onPress: () => router.back() },
      ]);
    } catch (error: any) {
      Alert.alert('Could not save schedule', error.message || 'Check the schedule and try again.');
    } finally {
      setSaving(false);
    }
  };

  const remove = () => {
    if (!id) return;
    Alert.alert('Remove schedule?', 'The workflow stays saved, but it will no longer run automatically.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: async () => {
        try {
          await api.deleteWorkflowSchedule(id);
          router.back();
        } catch (error: any) {
          Alert.alert('Could not remove schedule', error.message || 'Try again.');
        }
      } },
    ]);
  };

  if (loading) return <SafeAreaView style={styles.loading}><ActivityIndicator color={COLORS.coral} /></SafeAreaView>;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.title}>Schedule {workflow?.name || 'workflow'}</Text>
          <Text style={styles.subtitle}>Runs happen on the backend, even when this app is closed.</Text>

          {workflow && !workflow.enabled ? (
            <View style={styles.workflowOffNotice}>
              <Text style={styles.workflowOffTitle}>Workflow is off</Text>
              <Text style={styles.workflowOffText}>You can save the schedule now, but automatic runs require the workflow to be turned on.</Text>
            </View>
          ) : null}

          {existing ? (
            <View style={styles.nextRunRow}>
              <CalendarClock size={18} color={COLORS.coralDark} />
              <View style={styles.nextRunCopy}>
                <Text style={styles.nextRunLabel}>Next run</Text>
                <Text style={styles.nextRunValue}>{enabled ? nextRunLabel(existing.next_run_at) : 'Schedule paused'}</Text>
              </View>
              <Switch value={enabled} onValueChange={setEnabled} trackColor={{ false: '#D8D2CC', true: '#FF9B8E' }} thumbColor={enabled ? COLORS.coral : '#FFFFFF'} />
            </View>
          ) : null}

          <View style={styles.modeSwitch}>
            <TouchableOpacity style={[styles.modeButton, mode === 'once' && styles.modeButtonSelected]} onPress={() => setMode('once')}>
              <Clock3 size={17} color={mode === 'once' ? COLORS.coralDark : COLORS.muted} />
              <Text style={[styles.modeText, mode === 'once' && styles.modeTextSelected]}>At a time</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.modeButton, mode === 'window' && styles.modeButtonSelected]} onPress={() => setMode('window')}>
              <Repeat2 size={17} color={mode === 'window' ? COLORS.coralDark : COLORS.muted} />
              <Text style={[styles.modeText, mode === 'window' && styles.modeTextSelected]}>In a window</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>{mode === 'once' ? 'Run once' : 'Repeat during a window'}</Text>
            <Text style={styles.sectionHelp}>{mode === 'once' ? `Date and time are interpreted in ${timezone}.` : `The interval restarts at the beginning of each daily window in ${timezone}. Overnight windows are supported.`}</Text>
            {mode === 'once' ? (
              <View style={styles.fieldRow}>
                <View style={styles.fieldHalf}><Text style={styles.label}>Date</Text><TextInput style={styles.input} value={runDate} onChangeText={setRunDate} placeholder="YYYY-MM-DD" placeholderTextColor="#A59FA8" keyboardType="numbers-and-punctuation" /></View>
                <View style={styles.fieldHalf}><Text style={styles.label}>Time</Text><TextInput style={styles.input} value={runTime} onChangeText={setRunTime} placeholder="HH:MM" placeholderTextColor="#A59FA8" keyboardType="numbers-and-punctuation" /></View>
              </View>
            ) : (
              <>
                <View style={styles.fieldRow}>
                  <View style={styles.fieldHalf}><Text style={styles.label}>Window starts</Text><TextInput style={styles.input} value={windowStart} onChangeText={setWindowStart} placeholder="09:00" placeholderTextColor="#A59FA8" keyboardType="numbers-and-punctuation" /></View>
                  <View style={styles.fieldHalf}><Text style={styles.label}>Window ends</Text><TextInput style={styles.input} value={windowEnd} onChangeText={setWindowEnd} placeholder="17:00" placeholderTextColor="#A59FA8" keyboardType="numbers-and-punctuation" /></View>
                </View>
                <Text style={styles.label}>Repeat every</Text>
                <View style={styles.intervalField}><TextInput style={styles.intervalInput} value={interval} onChangeText={setIntervalValue} keyboardType="number-pad" /><Text style={styles.intervalUnit}>minutes</Text></View>
              </>
            )}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Starting input</Text>
            <Text style={styles.sectionHelp}>This is sent to the first workflow nodes on every scheduled run.</Text>
            <TextInput style={[styles.input, styles.promptInput]} value={inputText} onChangeText={setInputText} multiline textAlignVertical="top" placeholder="What should the workflow work on?" placeholderTextColor="#A59FA8" />
          </View>

          <TouchableOpacity style={[styles.saveButton, saving && styles.saveButtonDisabled]} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFFFFF" /> : <Check size={19} color="#FFFFFF" />}
            <Text style={styles.saveText}>{saving ? 'Saving…' : 'Save schedule'}</Text>
          </TouchableOpacity>
          {existing ? <TouchableOpacity style={styles.removeButton} onPress={remove}><Trash2 size={17} color="#A63F36" /><Text style={styles.removeText}>Remove schedule</Text></TouchableOpacity> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 }, safeArea: { flex: 1, backgroundColor: COLORS.canvas }, loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.canvas }, content: { padding: 20, paddingBottom: 48 },
  title: { color: COLORS.ink, fontSize: 28, lineHeight: 33, fontWeight: '800', letterSpacing: -0.7 }, subtitle: { color: COLORS.muted, fontSize: 14, lineHeight: 20, marginTop: 6, marginBottom: 22 },
  workflowOffNotice: { backgroundColor: '#FFF7F5', borderWidth: 1, borderColor: '#E7A59C', borderRadius: 12, padding: 13, marginBottom: 16 }, workflowOffTitle: { color: '#A63F36', fontSize: 13, fontWeight: '800' }, workflowOffText: { color: '#6D514E', fontSize: 12, lineHeight: 17, marginTop: 3 },
  nextRunRow: { minHeight: 68, flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: COLORS.coralSoft, borderRadius: 14, paddingHorizontal: 14, marginBottom: 16 }, nextRunCopy: { flex: 1 }, nextRunLabel: { color: COLORS.coralDark, fontSize: 11, fontWeight: '800' }, nextRunValue: { color: COLORS.ink, fontSize: 13, fontWeight: '700', marginTop: 2 },
  modeSwitch: { flexDirection: 'row', backgroundColor: '#ECE9E5', borderRadius: 12, padding: 4, marginBottom: 24 }, modeButton: { flex: 1, minHeight: 44, borderRadius: 9, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, modeButtonSelected: { backgroundColor: COLORS.surface }, modeText: { color: COLORS.muted, fontSize: 13, fontWeight: '700' }, modeTextSelected: { color: COLORS.coralDark },
  section: { marginBottom: 24 }, sectionTitle: { color: COLORS.ink, fontSize: 16, fontWeight: '800' }, sectionHelp: { color: COLORS.muted, fontSize: 12, lineHeight: 17, marginTop: 4, marginBottom: 13 }, fieldRow: { flexDirection: 'row', gap: 10, marginBottom: 13 }, fieldHalf: { flex: 1 }, label: { color: '#5E5862', fontSize: 12, fontWeight: '700', marginBottom: 7 },
  input: { minHeight: 48, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, borderRadius: 10, paddingHorizontal: 13, color: COLORS.ink, fontSize: 14 }, promptInput: { minHeight: 112, paddingTop: 13 },
  intervalField: { minHeight: 48, flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, borderRadius: 10 }, intervalInput: { flex: 1, paddingHorizontal: 13, color: COLORS.ink, fontSize: 14 }, intervalUnit: { color: COLORS.muted, fontSize: 13, paddingRight: 13 },
  saveButton: { minHeight: 52, borderRadius: 12, backgroundColor: COLORS.coral, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 }, saveButtonDisabled: { backgroundColor: '#CFC9C4' }, saveText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  removeButton: { minHeight: 48, marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, removeText: { color: '#A63F36', fontSize: 13, fontWeight: '700' },
});
