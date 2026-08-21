import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Audio } from 'expo-av';
import { Mic, Square } from 'lucide-react-native';

interface VoiceRecorderProps {
  onRecordingComplete: (uri: string) => void;
  onCancel?: () => void;
  title?: string;
  subtitle?: string;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  onRecordingComplete,
  onCancel,
  title = 'Tell me what you want to create',
  subtitle = 'Speak naturally. We will convert your voice into an agent workflow.',
}) => {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRecording) {
      interval = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setSeconds(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  useEffect(() => {
    return () => {
      if (recording) {
        recording.stopAndUnloadAsync().catch(() => {});
      }
    };
  }, [recording]);

  const startRecording = async () => {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (permission.status !== 'granted') {
        alert('Permission to access microphone was denied');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording: newRecording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(newRecording);
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording', err);
    }
  };

  const stopRecording = async () => {
    if (!recording) return;
    try {
      setIsRecording(false);
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (uri) {
        onRecordingComplete(uri);
      }
    } catch (err) {
      console.error('Failed to stop recording', err);
    }
  };

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>{subtitle}</Text>

      <View style={styles.recordSection}>
        <View style={[styles.pulseRing, isRecording && styles.pulseRingActive]}>
          <TouchableOpacity
            activeOpacity={0.8}
            style={[styles.micButton, isRecording && styles.micButtonActive]}
            onPress={isRecording ? stopRecording : startRecording}
          >
            {isRecording ? (
              <Square size={36} color="#FFFFFF" />
            ) : (
              <Mic size={40} color="#FFFFFF" />
            )}
          </TouchableOpacity>
        </View>

        <Text style={styles.statusText}>
          {isRecording ? `Recording... ${formatTime(seconds)}` : 'Tap to start recording'}
        </Text>

        {isRecording && (
          <TouchableOpacity style={styles.stopButton} onPress={stopRecording}>
            <Text style={styles.stopButtonText}>Stop Recording</Text>
          </TouchableOpacity>
        )}

        {onCancel && !isRecording && (
          <TouchableOpacity style={styles.cancelButton} onPress={onCancel}>
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    padding: 24,
  },
  title: {
    color: '#F8FAFC',
    fontSize: 22,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    color: '#94A3B8',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 40,
    maxWidth: 300,
  },
  recordSection: {
    alignItems: 'center',
  },
  pulseRing: {
    width: 130,
    height: 130,
    borderRadius: 65,
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  pulseRingActive: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 2,
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  micButton: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: '#3B82F6',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#3B82F6',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  micButtonActive: {
    backgroundColor: '#EF4444',
    shadowColor: '#EF4444',
  },
  statusText: {
    color: '#E2E8F0',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 24,
  },
  stopButton: {
    backgroundColor: '#EF4444',
    paddingHorizontal: 28,
    paddingVertical: 12,
    borderRadius: 24,
  },
  stopButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  cancelButton: {
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  cancelButtonText: {
    color: '#64748B',
    fontSize: 14,
  },
});
