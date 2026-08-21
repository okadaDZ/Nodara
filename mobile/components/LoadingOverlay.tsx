import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  visible,
  message = 'Generating Workflow...',
}) => {
  if (!visible) return null;

  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={message}
      style={styles.backdrop}
    >
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#FF6D5A" />
        <Text style={styles.text}>{message}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(41, 38, 45, 0.46)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    zIndex: 9999,
    elevation: 9999,
  },
  container: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingHorizontal: 28,
    paddingVertical: 24,
    alignItems: 'center',
    minWidth: 220,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 16,
    elevation: 10,
  },
  text: {
    color: '#29262D',
    fontSize: 15,
    fontWeight: '600',
    marginTop: 16,
    textAlign: 'center',
  },
});
