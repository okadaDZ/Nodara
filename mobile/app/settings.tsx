import React, { PropsWithChildren, useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, Animated, Modal, PanResponder, SafeAreaView, ScrollView, StyleSheet, Switch,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { Check, Eye, EyeOff, LockKeyhole, Pencil, RefreshCw, Server, Trash2, X } from 'lucide-react-native';
import { api } from '@/services/api';
import { DEFAULT_SETTINGS, LocalSettings, loadLocalModels, loadSettings, saveLocalModels, saveSettings } from '@/services/settings';
import { AvailableModel } from '@/types/workflow';

const SWIPE_WIDTH = 84;
type SwipeDirection = -1 | 0 | 1;

function SwipeModelRow({ name, onEdit, onDelete, children }: PropsWithChildren<{
  name: string;
  onEdit: () => void;
  onDelete: () => void;
}>) {
  const translateX = useRef(new Animated.Value(0)).current;
  const openRef = useRef<SwipeDirection>(0);

  const settle = useCallback((direction: SwipeDirection) => {
    openRef.current = direction;
    Animated.spring(translateX, {
      toValue: direction * SWIPE_WIDTH,
      useNativeDriver: true,
      speed: 24,
      bounciness: 0,
    }).start();
  }, [translateX]);

  const runAction = (action: () => void) => {
    settle(0);
    action();
  };

  const panResponder = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, gesture) =>
      Math.abs(gesture.dx) > 8 && Math.abs(gesture.dx) > Math.abs(gesture.dy) * 1.25,
    onPanResponderMove: (_, gesture) => {
      const origin = openRef.current * SWIPE_WIDTH;
      translateX.setValue(Math.max(-SWIPE_WIDTH, Math.min(SWIPE_WIDTH, origin + gesture.dx)));
    },
    onPanResponderRelease: (_, gesture) => {
      const projected = openRef.current * SWIPE_WIDTH + gesture.dx;
      if (projected < -SWIPE_WIDTH * 0.42 || gesture.vx < -0.45) settle(-1);
      else if (projected > SWIPE_WIDTH * 0.42 || gesture.vx > 0.45) settle(1);
      else settle(0);
    },
    onPanResponderTerminate: () => settle(openRef.current),
  })).current;

  return (
    <View style={styles.swipeModelContainer}>
      <TouchableOpacity style={styles.editAction} onPress={() => runAction(onEdit)} accessibilityLabel={`Edit ${name}`}>
        <Pencil size={18} color="#FFFFFF" />
        <Text style={styles.actionText}>Edit</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.deleteAction} onPress={() => runAction(onDelete)} accessibilityLabel={`Delete ${name}`}>
        <Trash2 size={18} color="#FFFFFF" />
        <Text style={styles.actionText}>Delete</Text>
      </TouchableOpacity>
      <Animated.View style={{ transform: [{ translateX }] }} {...panResponder.panHandlers}>
        {children}
      </Animated.View>
    </View>
  );
}

export default function SettingsScreen() {
  const [settings, setSettings] = useState<LocalSettings>(DEFAULT_SETTINGS);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [backendDefault, setBackendDefault] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingModel, setEditingModel] = useState<AvailableModel | null>(null);
  const [editedModelId, setEditedModelId] = useState('');
  const [editedModelName, setEditedModelName] = useState('');

  useEffect(() => {
    loadSettings()
      .then(async (saved) => {
        setSettings(saved);
        const localModels = await loadLocalModels();
        setModels(localModels);
        try {
          const catalog = await api.getModels();
          setBackendDefault(catalog.default_model);
          const editableModels = catalog.models.filter((model) => model.id !== catalog.default_model);
          setModels(editableModels);
          await saveLocalModels(editableModels);
        } catch {
          // The screen remains editable when the backend is offline.
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const update = <K extends keyof LocalSettings>(key: K, value: LocalSettings[K]) =>
    setSettings((current) => ({ ...current, [key]: value }));

  const loadModels = async () => {
    try {
      setLoadingModels(true);
      await saveSettings(settings);
      const catalog = await api.getModels();
      setBackendDefault(catalog.default_model);
      const editableModels = catalog.models.filter((model) => model.id !== catalog.default_model);
      setModels(editableModels);
      await saveLocalModels(editableModels);
    } catch (error: any) {
      Alert.alert('Could not load models', error.message || 'Check the backend and provider settings.');
    } finally {
      setLoadingModels(false);
    }
  };

  const startEditingModel = (model: AvailableModel) => {
    setEditingModel(model);
    setEditedModelId(model.id);
    setEditedModelName(model.name);
  };

  const commitModelEdit = async () => {
    const id = editedModelId.trim();
    const name = editedModelName.trim();
    if (!editingModel || !id || !name) {
      Alert.alert('Model details required', 'Enter both the model ID and display name.');
      return;
    }
    if (id === backendDefault || models.some((model) => model.id === id && model.id !== editingModel.id)) {
      Alert.alert('Model ID already used', 'Choose a unique model ID.');
      return;
    }
    const nextModels = models.map((model) => model.id === editingModel.id ? { id, name } : model);
    setModels(nextModels);
    if (settings.globalModel === editingModel.id) update('globalModel', id);
    await saveLocalModels(nextModels);
    setEditingModel(null);
  };

  const confirmDeleteModel = (model: AvailableModel) => {
    Alert.alert('Delete model?', `Remove “${model.name}” from this device?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          const nextModels = models.filter((item) => item.id !== model.id);
          setModels(nextModels);
          if (settings.globalModel === model.id) update('globalModel', '');
          await saveLocalModels(nextModels);
        },
      },
    ]);
  };

  const save = async () => {
    if (!settings.backendUrl.trim()) {
      Alert.alert('Backend URL required', 'Enter the address of your Nodara backend.');
      return;
    }
    if (settings.useCustomProvider && (!settings.providerBaseUrl.trim() || !settings.apiKey.trim())) {
      Alert.alert('Provider details required', 'Enter both the provider URL and API key.');
      return;
    }
    try {
      setSaving(true);
      await saveSettings(settings);
      const catalog = models.length ? { default_model: backendDefault } : await api.getModels();
      await api.applyModelToAllWorkflows(settings.globalModel || catalog.default_model);
      Alert.alert('Settings saved', 'New and existing nodes without an override will use this model.');
    } catch (error: any) {
      Alert.alert('Save failed', error.message || 'Could not save settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <SafeAreaView style={styles.loading}><ActivityIndicator color="#FF6D5A" /></SafeAreaView>;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.intro}>Connection details and model defaults stay on this device.</Text>

        <Text style={styles.sectionTitle}>Backend</Text>
        <View style={styles.fieldGroup}>
          <Text style={styles.label}>Nodara backend URL</Text>
          <TextInput style={styles.input} value={settings.backendUrl} onChangeText={(value) => update('backendUrl', value)} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="http://192.168.1.10:8000" placeholderTextColor="#A59FA8" />
        </View>

        <View style={styles.divider} />
        <View style={styles.switchRow}>
          <View style={styles.switchCopy}>
            <Text style={styles.sectionTitle}>Custom LLM provider</Text>
            <Text style={styles.help}>Off uses the backend’s configured provider and key.</Text>
          </View>
          <Switch value={settings.useCustomProvider} onValueChange={(value) => update('useCustomProvider', value)} trackColor={{ false: '#D8D2CC', true: '#FF9B8E' }} thumbColor={settings.useCustomProvider ? '#FF6D5A' : '#FFFFFF'} />
        </View>

        {settings.useCustomProvider ? (
          <View style={styles.providerFields}>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>OpenAI-compatible API URL</Text>
              <TextInput style={styles.input} value={settings.providerBaseUrl} onChangeText={(value) => update('providerBaseUrl', value)} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="https://api.openai.com/v1" placeholderTextColor="#A59FA8" />
            </View>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>API key</Text>
              <View style={styles.keyField}>
                <TextInput style={styles.keyInput} value={settings.apiKey} onChangeText={(value) => update('apiKey', value)} autoCapitalize="none" autoCorrect={false} secureTextEntry={!showKey} placeholder="sk-…" placeholderTextColor="#A59FA8" />
                <TouchableOpacity style={styles.eyeButton} onPress={() => setShowKey((value) => !value)} accessibilityLabel={showKey ? 'Hide API key' : 'Show API key'}>
                  {showKey ? <EyeOff size={18} color="#756F79" /> : <Eye size={18} color="#756F79" />}
                </TouchableOpacity>
              </View>
              <Text style={styles.secureNote}>Stored in this device’s secure keychain.</Text>
            </View>
          </View>
        ) : null}

        <View style={styles.modelHeader}>
          <View style={styles.switchCopy}>
            <Text style={styles.sectionTitle}>Default model</Text>
            <Text style={styles.help}>Agents use this unless you override the model inside a node.</Text>
          </View>
          <TouchableOpacity style={styles.refreshButton} onPress={loadModels} disabled={loadingModels}>
            {loadingModels ? <ActivityIndicator size="small" color="#B9502E" /> : <RefreshCw size={16} color="#B9502E" />}
            <Text style={styles.refreshText}>Load models</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={[styles.modelRow, !settings.globalModel && styles.modelRowSelected]} onPress={() => update('globalModel', '')}>
          <Server size={17} color={!settings.globalModel ? '#B9502E' : '#756F79'} />
          <View style={styles.modelCopy}><Text style={styles.modelName}>Backend default</Text><Text style={styles.modelMeta}>{backendDefault || 'Managed by the backend'}</Text></View>
          <LockKeyhole size={15} color="#A59FA8" />
          {!settings.globalModel ? <Check size={18} color="#B9502E" /> : null}
        </TouchableOpacity>
        {models.length ? <Text style={styles.swipeHint}>Swipe right to edit · left to delete</Text> : null}
        {models.map((model) => {
          const selected = settings.globalModel === model.id;
          return <SwipeModelRow key={model.id} name={model.name} onEdit={() => startEditingModel(model)} onDelete={() => confirmDeleteModel(model)}>
            <TouchableOpacity style={[styles.modelRow, styles.editableModelRow, selected && styles.modelRowSelected]} onPress={() => update('globalModel', model.id)}>
              <View style={styles.modelCopy}><Text style={styles.modelName}>{model.name}</Text><Text style={styles.modelMeta}>{model.id}</Text></View>
              {selected ? <Check size={18} color="#B9502E" /> : null}
            </TouchableOpacity>
          </SwipeModelRow>;
        })}

        <TouchableOpacity style={styles.saveButton} onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator color="#FFFFFF" /> : <Check size={19} color="#FFFFFF" />}
          <Text style={styles.saveText}>{saving ? 'Saving…' : 'Save settings'}</Text>
        </TouchableOpacity>
      </ScrollView>

      <Modal visible={Boolean(editingModel)} transparent animationType="fade" onRequestClose={() => setEditingModel(null)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <View><Text style={styles.modalTitle}>Edit model</Text><Text style={styles.modalSubtitle}>Saved only on this device.</Text></View>
              <TouchableOpacity style={styles.closeButton} onPress={() => setEditingModel(null)} accessibilityLabel="Close model editor"><X size={20} color="#756F79" /></TouchableOpacity>
            </View>
            <Text style={styles.label}>Display name</Text>
            <TextInput style={styles.input} value={editedModelName} onChangeText={setEditedModelName} autoCapitalize="none" autoCorrect={false} />
            <Text style={[styles.label, styles.modalFieldLabel]}>Model ID</Text>
            <TextInput style={styles.input} value={editedModelId} onChangeText={setEditedModelId} autoCapitalize="none" autoCorrect={false} />
            <TouchableOpacity style={styles.modalSaveButton} onPress={commitModelEdit}><Check size={18} color="#FFFFFF" /><Text style={styles.modalSaveText}>Save model</Text></TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F7F5F2' }, loading: { flex: 1, backgroundColor: '#F7F5F2', alignItems: 'center', justifyContent: 'center' },
  content: { padding: 20, paddingBottom: 48 }, title: { color: '#29262D', fontSize: 30, fontWeight: '800', letterSpacing: -0.8 },
  intro: { color: '#756F79', fontSize: 14, lineHeight: 20, marginTop: 6, marginBottom: 28 }, sectionTitle: { color: '#29262D', fontSize: 16, fontWeight: '800' },
  fieldGroup: { marginTop: 12 }, label: { color: '#5E5862', fontSize: 12, fontWeight: '700', marginBottom: 7 },
  input: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D8D2CC', borderRadius: 10, color: '#29262D', fontSize: 15, paddingHorizontal: 13, paddingVertical: 12 },
  divider: { height: 1, backgroundColor: '#DDD8D3', marginVertical: 24 }, switchRow: { flexDirection: 'row', alignItems: 'center', gap: 18 }, switchCopy: { flex: 1 },
  help: { color: '#756F79', fontSize: 12, lineHeight: 17, marginTop: 4 }, providerFields: { marginTop: 8, gap: 4 },
  keyField: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D8D2CC', borderRadius: 10, alignItems: 'center' }, keyInput: { flex: 1, color: '#29262D', fontSize: 15, paddingHorizontal: 13, paddingVertical: 12 }, eyeButton: { padding: 12 }, secureNote: { color: '#756F79', fontSize: 11, marginTop: 6 },
  modelHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginTop: 28, marginBottom: 10 }, refreshButton: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 7, paddingHorizontal: 8 }, refreshText: { color: '#B9502E', fontSize: 12, fontWeight: '700' },
  modelRow: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: 1, borderBottomColor: '#E3DEDA', paddingHorizontal: 10 }, modelRowSelected: { backgroundColor: '#FFF0ED' }, modelCopy: { flex: 1 }, modelName: { color: '#29262D', fontSize: 14, fontWeight: '700' }, modelMeta: { color: '#756F79', fontSize: 11, marginTop: 2 },
  swipeHint: { color: '#8B858E', fontSize: 11, marginTop: 10, marginBottom: 5, paddingHorizontal: 10 },
  swipeModelContainer: { overflow: 'hidden', backgroundColor: '#D94A43' }, editableModelRow: { backgroundColor: '#F7F5F2' },
  editAction: { position: 'absolute', left: 0, top: 0, bottom: 0, width: SWIPE_WIDTH, backgroundColor: '#6D5BD0', alignItems: 'center', justifyContent: 'center', gap: 3 },
  deleteAction: { position: 'absolute', right: 0, top: 0, bottom: 0, width: SWIPE_WIDTH, backgroundColor: '#D94A43', alignItems: 'center', justifyContent: 'center', gap: 3 }, actionText: { color: '#FFFFFF', fontSize: 11, fontWeight: '800' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(41,38,45,0.38)', alignItems: 'center', justifyContent: 'center', padding: 20 }, modalCard: { width: '100%', maxWidth: 430, backgroundColor: '#FFFFFF', borderRadius: 18, padding: 20 },
  modalHeader: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 22 }, modalTitle: { color: '#29262D', fontSize: 20, fontWeight: '800' }, modalSubtitle: { color: '#756F79', fontSize: 12, marginTop: 3 }, closeButton: { marginLeft: 'auto', padding: 5 }, modalFieldLabel: { marginTop: 16 },
  modalSaveButton: { minHeight: 48, borderRadius: 12, marginTop: 22, backgroundColor: '#FF6D5A', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 }, modalSaveText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  saveButton: { marginTop: 30, minHeight: 52, borderRadius: 12, backgroundColor: '#FF6D5A', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 }, saveText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
});
