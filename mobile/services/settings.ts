import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { getApiBaseUrl } from '@/constants/config';
import { AvailableModel } from '@/types/workflow';

const SETTINGS_KEY = 'nodara.settings.v1';
const MODELS_KEY = 'nodara.models.v1';

export interface LocalSettings {
  backendUrl: string;
  useCustomProvider: boolean;
  providerBaseUrl: string;
  apiKey: string;
  globalModel: string;
}

export const DEFAULT_SETTINGS: LocalSettings = {
  backendUrl: getApiBaseUrl(),
  useCustomProvider: false,
  providerBaseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  globalModel: '',
};

let cachedSettings: LocalSettings | null = null;

async function readValue(): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(SETTINGS_KEY) ?? null;
  return await SecureStore.getItemAsync(SETTINGS_KEY);
}

async function writeValue(value: string): Promise<void> {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.setItem(SETTINGS_KEY, value);
    return;
  }
  await SecureStore.setItemAsync(SETTINGS_KEY, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

async function readModelsValue(): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(MODELS_KEY) ?? null;
  return await SecureStore.getItemAsync(MODELS_KEY);
}

async function writeModelsValue(value: string): Promise<void> {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.setItem(MODELS_KEY, value);
    return;
  }
  await SecureStore.setItemAsync(MODELS_KEY, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function loadSettings(): Promise<LocalSettings> {
  if (cachedSettings) return cachedSettings;
  try {
    const saved = await readValue();
    cachedSettings = saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : { ...DEFAULT_SETTINGS };
  } catch {
    cachedSettings = { ...DEFAULT_SETTINGS };
  }
  return cachedSettings!;
}

export async function saveSettings(settings: LocalSettings): Promise<void> {
  cachedSettings = {
    ...settings,
    backendUrl: settings.backendUrl.trim().replace(/\/$/, ''),
    providerBaseUrl: settings.providerBaseUrl.trim().replace(/\/$/, ''),
    apiKey: settings.apiKey.trim(),
    globalModel: settings.globalModel.trim(),
  };
  await writeValue(JSON.stringify(cachedSettings));
}

export async function loadLocalModels(): Promise<AvailableModel[]> {
  try {
    const saved = await readModelsValue();
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

export async function saveLocalModels(models: AvailableModel[]): Promise<void> {
  await writeModelsValue(JSON.stringify(models));
}

export function clearSettingsCache(): void {
  cachedSettings = null;
}
