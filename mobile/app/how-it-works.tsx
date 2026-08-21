import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ArrowRight, Camera, GitBranch } from 'lucide-react-native';

import { api } from '@/services/api';

const STEPS = [
  {
    title: 'Start with boxes and arrows',
    body: 'Photograph the whole drawing. Labels can be handwritten; relationships matter most.',
  },
  {
    title: 'Nodara rebuilds the graph',
    body: 'It detects agents, parallel branches, joins, routes, and the order in which work should happen.',
  },
  {
    title: 'Review, edit, and run',
    body: 'Choose suggested improvements, assign models, adjust any node, then run or export the workflow.',
  },
];

export default function HowItWorksScreen() {
  const router = useRouter();
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [openingDemo, setOpeningDemo] = useState(false);

  useEffect(() => {
    api.getDemoImageUrl().then(setImageUrl).catch(() => setImageFailed(true));
  }, []);

  const openDemo = async () => {
    try {
      setOpeningDemo(true);
      const workflow = await api.getDemoWorkflow();
      router.replace(`/workflow/${workflow.id}`);
    } catch (err: any) {
      Alert.alert('Demo unavailable', err.message || 'Could not open the generated workflow.');
    } finally {
      setOpeningDemo(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>From a sketch to a working graph</Text>
        <Text style={styles.subtitle}>
          This is the same hand-drawn example used to test Nodara’s node and connection detection.
        </Text>

        <View style={styles.imageFrame}>
          {imageUrl && !imageFailed ? (
            <Image
              source={{ uri: imageUrl }}
              style={styles.exampleImage}
              resizeMode="contain"
              onError={() => setImageFailed(true)}
              accessibilityLabel="Hand-drawn parallel workflow testing example"
            />
          ) : imageFailed ? (
            <View style={styles.imageFallback}>
              <Camera size={24} color="#756F79" />
              <Text style={styles.imageFallbackText}>Connect to the backend to load the example drawing.</Text>
            </View>
          ) : (
            <ActivityIndicator color="#FF6D5A" />
          )}
        </View>

        <View style={styles.steps}>
          {STEPS.map((step, index) => (
            <View key={step.title} style={styles.stepRow}>
              <View style={styles.stepRail}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{index + 1}</Text>
                </View>
                {index < STEPS.length - 1 ? <View style={styles.stepLine} /> : null}
              </View>
              <View style={styles.stepCopy}>
                <Text style={styles.stepTitle}>{step.title}</Text>
                <Text style={styles.stepBody}>{step.body}</Text>
              </View>
            </View>
          ))}
        </View>

        <TouchableOpacity
          activeOpacity={0.86}
          style={styles.demoButton}
          onPress={openDemo}
          disabled={openingDemo}
        >
          {openingDemo
            ? <ActivityIndicator color="#FFFFFF" />
            : <GitBranch size={19} color="#FFFFFF" />}
          <Text style={styles.demoButtonText}>Open the generated demo</Text>
          {!openingDemo ? <ArrowRight size={19} color="#FFFFFF" /> : null}
        </TouchableOpacity>

        <TouchableOpacity style={styles.scanButton} onPress={() => router.push('/create/photo')}>
          <Camera size={17} color="#29262D" />
          <Text style={styles.scanButtonText}>Scan my own sketch</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F7F5F2' },
  content: { padding: 20, paddingBottom: 44 },
  title: { color: '#29262D', fontSize: 29, lineHeight: 34, fontWeight: '800', letterSpacing: -0.8, maxWidth: 340 },
  subtitle: { color: '#756F79', fontSize: 14, lineHeight: 21, marginTop: 9, marginBottom: 22, maxWidth: 350 },
  imageFrame: { height: 245, borderRadius: 16, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#DDD8D3', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  exampleImage: { width: '100%', height: '100%' },
  imageFallback: { paddingHorizontal: 30, alignItems: 'center', gap: 10 },
  imageFallbackText: { color: '#756F79', fontSize: 13, lineHeight: 19, textAlign: 'center' },
  steps: { marginTop: 28, marginBottom: 24 },
  stepRow: { minHeight: 92, flexDirection: 'row' },
  stepRail: { width: 34, alignItems: 'center', marginRight: 12 },
  stepNumber: { width: 30, height: 30, borderRadius: 10, backgroundColor: '#FFF0ED', alignItems: 'center', justifyContent: 'center' },
  stepNumberText: { color: '#B9502E', fontSize: 13, fontWeight: '800' },
  stepLine: { flex: 1, width: 1, marginVertical: 5, backgroundColor: '#DDD8D3' },
  stepCopy: { flex: 1, paddingTop: 3, paddingBottom: 18 },
  stepTitle: { color: '#29262D', fontSize: 15, lineHeight: 20, fontWeight: '800' },
  stepBody: { color: '#756F79', fontSize: 13, lineHeight: 19, marginTop: 4 },
  demoButton: { minHeight: 56, borderRadius: 14, backgroundColor: '#FF6D5A', paddingHorizontal: 17, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9 },
  demoButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800', flex: 1, textAlign: 'center' },
  scanButton: { minHeight: 48, marginTop: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  scanButtonText: { color: '#29262D', fontSize: 13, fontWeight: '700' },
});
