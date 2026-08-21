import Constants from 'expo-constants';

const DEFAULT_API_URL = 'http://localhost:8000';

export const getApiBaseUrl = (): string => {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL.replace(/\/$/, '');
  }

  // Fallback to host URI if running in Expo Go on real device
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const ip = hostUri.split(':')[0];
    return `http://${ip}:8000`;
  }

  return DEFAULT_API_URL;
};

export const API_BASE_URL = getApiBaseUrl();
