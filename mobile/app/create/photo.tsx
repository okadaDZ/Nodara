import React, { useState } from 'react';
import {
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
import * as ImagePicker from 'expo-image-picker';
import { api } from '@/services/api';
import { LoadingOverlay } from '@/components/LoadingOverlay';
import { WorkflowBuildProgress } from '@/components/WorkflowBuildProgress';
import { ImageWorkflowResult, ImageWorkflowStage } from '@/types/workflow';
import { ArrowRight, Camera, Check, Image as ImageIcon, RotateCcw, Workflow } from 'lucide-react-native';

export default function PhotoCreateScreen() {
  const router = useRouter();
  const [selectedImage, setSelectedImage] = useState<{ uri: string; mimeType?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [buildStage, setBuildStage] = useState<ImageWorkflowStage>('queued');
  const [review, setReview] = useState<ImageWorkflowResult | null>(null);
  const [selectedRecommendations, setSelectedRecommendations] = useState<Set<number>>(new Set());

  const takePhoto = async () => {
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission Denied', 'Camera permission is required to photograph workflows.');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets[0]) {
        const asset = result.assets[0];
        setSelectedImage({ uri: asset.uri, mimeType: asset.mimeType ?? undefined });
      }
    } catch (err: any) {
      Alert.alert('Camera Error', err.message || 'Could not open camera.');
    }
  };

  const pickImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets[0]) {
        const asset = result.assets[0];
        setSelectedImage({ uri: asset.uri, mimeType: asset.mimeType ?? undefined });
      }
    } catch (err: any) {
      Alert.alert('Gallery Error', err.message || 'Could not pick image.');
    }
  };

  const handleScan = async () => {
    if (!selectedImage) return;

    try {
      setLoading(true);
      setBuildStage('queued');
      const result = await api.createFromImageWithProgress(
        selectedImage.uri,
        selectedImage.mimeType,
        setBuildStage,
      );
      const openWorkflow = () => router.replace(`/workflow/${result.workflow.id}`);
      if (result.analysis.requires_redraw || result.analysis.requires_user_decision) {
        setReview(result);
        setSelectedRecommendations(new Set(result.analysis.recommendations.map((_, index) => index)));
      } else {
        openWorkflow();
      }
    } catch (err: any) {
      Alert.alert('Scan Failed', err.message || 'Could not parse workflow diagram.');
    } finally {
      setLoading(false);
    }
  };

  const toggleRecommendation = (index: number) => {
    setSelectedRecommendations((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const applySelectedRecommendations = async () => {
    if (!review || selectedRecommendations.size === 0) return;
    const instructions = review.analysis.recommendations
      .filter((_, index) => selectedRecommendations.has(index))
      .map((item) => item.instruction)
      .join('\n');
    try {
      setLoading(true);
      const updated = await api.aiEditWorkflow(review.workflow.id, instructions);
      router.replace(`/workflow/${updated.id}`);
    } catch (error: any) {
      Alert.alert('Could not apply changes', error.message || 'Your workflow is saved. You can edit it manually.');
    } finally {
      setLoading(false);
    }
  };

  const redrawWorkflow = async () => {
    if (!review) return;
    try {
      await api.deleteWorkflow(review.workflow.id);
    } catch {
      // Returning to the scanner matters more than blocking on cleanup.
    }
    setReview(null);
    setSelectedRecommendations(new Set());
    setSelectedImage(null);
  };

  if (review) {
    const recommendationCount = review.analysis.recommendations.length;
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />
        <ScrollView contentContainerStyle={styles.reviewContent} showsVerticalScrollIndicator={false}>
          <View style={styles.reviewHeader}>
            <View style={styles.reviewIcon}>
              <Workflow size={22} color="#FF6D5A" />
            </View>
            <View style={styles.reviewHeaderCopy}>
              <Text style={styles.reviewTitle}>
                {review.analysis.requires_redraw ? 'This sketch needs a decision' : 'Choose what to improve'}
              </Text>
              <Text style={styles.reviewSubtitle}>{review.analysis.summary}</Text>
            </View>
          </View>

          {recommendationCount > 0 ? (
            <View style={styles.recommendationSection}>
              <View style={styles.recommendationHeading}>
                <Text style={styles.recommendationTitle}>Suggested changes</Text>
                <Text style={styles.selectionCount}>
                  {selectedRecommendations.size} of {recommendationCount} selected
                </Text>
              </View>
              <Text style={styles.recommendationHint}>Tap a point to include or leave it out.</Text>

              <View style={styles.recommendationList}>
                {review.analysis.recommendations.map((item, index) => {
                  const selected = selectedRecommendations.has(index);
                  return (
                    <TouchableOpacity
                      key={`${item.title}-${index}`}
                      activeOpacity={0.78}
                      style={[styles.recommendationRow, selected && styles.recommendationRowSelected]}
                      onPress={() => toggleRecommendation(index)}
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: selected }}
                      accessibilityLabel={`${item.title}. ${item.rationale}`}
                    >
                      <View style={[styles.checkbox, selected && styles.checkboxSelected]}>
                        {selected ? <Check size={16} strokeWidth={3} color="#FFFFFF" /> : null}
                      </View>
                      <View style={styles.recommendationCopy}>
                        <Text style={styles.recommendationItemTitle}>{item.title}</Text>
                        <Text style={styles.recommendationRationale}>{item.rationale}</Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          ) : (
            <View style={styles.redrawNotice}>
              <Text style={styles.redrawNoticeTitle}>The structure is not clear enough</Text>
              <Text style={styles.redrawNoticeText}>
                Photograph the full drawing again with every box, label, and arrow visible—or continue with the current extraction.
              </Text>
            </View>
          )}

          <View style={styles.reviewActions}>
            {recommendationCount > 0 ? (
              <TouchableOpacity
                activeOpacity={0.86}
                style={[styles.applyButton, selectedRecommendations.size === 0 && styles.applyButtonDisabled]}
                onPress={applySelectedRecommendations}
                disabled={selectedRecommendations.size === 0 || loading}
              >
                <Text style={styles.applyButtonText}>
                  Apply {selectedRecommendations.size} {selectedRecommendations.size === 1 ? 'change' : 'changes'}
                </Text>
                <ArrowRight size={19} color="#FFFFFF" />
              </TouchableOpacity>
            ) : null}

            <TouchableOpacity
              style={styles.skipButton}
              onPress={() => router.replace(`/workflow/${review.workflow.id}`)}
              disabled={loading}
            >
              <Text style={styles.skipButtonText}>{recommendationCount ? 'Skip these changes' : 'Continue anyway'}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.redrawButton} onPress={redrawWorkflow} disabled={loading}>
              <RotateCcw size={17} color="#756F79" />
              <Text style={styles.redrawButtonText}>Redraw and scan again</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
        <LoadingOverlay visible={loading} message="Applying selected changes…" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.eyebrow}>NEW FLOW</Text>
        <Text style={styles.title}>Show Nodara your sketch</Text>
        <Text style={styles.subtitle}>
          Keep every box and connecting arrow inside the frame. Paper sketches work well.
        </Text>

        {selectedImage ? (
          <View style={styles.previewCard}>
            <Image source={{ uri: selectedImage.uri }} style={styles.previewImage} resizeMode="contain" />
            <View style={styles.previewActions}>
              <TouchableOpacity style={styles.reselectButton} onPress={takePhoto}>
                <Camera size={18} color="#94A3B8" />
                <Text style={styles.reselectText}>Retake</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.reselectButton} onPress={pickImage}>
                <ImageIcon size={18} color="#94A3B8" />
                <Text style={styles.reselectText}>Choose another</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              activeOpacity={0.8}
              style={styles.scanButton}
              onPress={handleScan}
              disabled={loading}
            >
              <Workflow size={20} color="#FFFFFF" />
              <Text style={styles.scanButtonText}>Read this diagram</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.pickerContainer}>
            <TouchableOpacity activeOpacity={0.8} style={styles.cameraBox} onPress={takePhoto}>
              <View style={styles.iconCircle}>
                <Camera size={32} color="#FF6D5A" />
              </View>
              <Text style={styles.boxTitle}>Open camera</Text>
              <Text style={styles.boxDesc}>Center the full diagram in frame</Text>
            </TouchableOpacity>

            <TouchableOpacity activeOpacity={0.8} style={styles.galleryBox} onPress={pickImage}>
              <ImageIcon size={22} color="#5E5862" />
              <Text style={styles.galleryText}>Choose an existing photo</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      <WorkflowBuildProgress visible={loading} stage={buildStage} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F7F5F2',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  eyebrow: {
    color: '#B9502E',
    fontSize: 12,
    fontWeight: '700',
    marginTop: 12,
    marginBottom: 10,
  },
  title: {
    color: '#29262D',
    fontSize: 30,
    lineHeight: 34,
    fontWeight: '800',
    letterSpacing: -0.8,
    marginBottom: 8,
  },
  subtitle: {
    color: '#756F79',
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 28,
  },
  pickerContainer: {
    gap: 16,
  },
  cameraBox: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#CFC8C2',
    borderStyle: 'dashed',
    paddingVertical: 42,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 16,
    backgroundColor: '#FFF0ED',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  boxTitle: {
    color: '#29262D',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  boxDesc: {
    color: '#756F79',
    fontSize: 13,
  },
  galleryBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    gap: 10,
  },
  galleryText: {
    color: '#29262D',
    fontSize: 15,
    fontWeight: '600',
  },
  previewCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#DDD8D3',
  },
  previewImage: {
    width: '100%',
    height: 240,
    borderRadius: 12,
    backgroundColor: '#EFEBE7',
    marginBottom: 16,
  },
  previewActions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 20,
  },
  reselectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    padding: 8,
  },
  reselectText: {
    color: '#756F79',
    fontSize: 14,
    fontWeight: '500',
  },
  scanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF6D5A',
    borderRadius: 14,
    paddingVertical: 16,
    gap: 8,
  },
  scanButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  reviewContent: { padding: 20, paddingBottom: 44 },
  reviewHeader: { flexDirection: 'row', alignItems: 'flex-start', paddingTop: 12, marginBottom: 30 },
  reviewIcon: { width: 48, height: 48, borderRadius: 14, backgroundColor: '#FFF0ED', alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  reviewHeaderCopy: { flex: 1 },
  reviewTitle: { color: '#29262D', fontSize: 25, lineHeight: 30, fontWeight: '800', letterSpacing: -0.6 },
  reviewSubtitle: { color: '#756F79', fontSize: 14, lineHeight: 21, marginTop: 8 },
  recommendationSection: { marginBottom: 26 },
  recommendationHeading: { flexDirection: 'row', alignItems: 'baseline' },
  recommendationTitle: { color: '#29262D', fontSize: 17, fontWeight: '800' },
  selectionCount: { color: '#756F79', fontSize: 12, fontWeight: '600', marginLeft: 'auto' },
  recommendationHint: { color: '#756F79', fontSize: 13, marginTop: 5, marginBottom: 13 },
  recommendationList: { borderTopWidth: 1, borderTopColor: '#DDD8D3' },
  recommendationRow: { minHeight: 92, paddingVertical: 15, borderBottomWidth: 1, borderBottomColor: '#DDD8D3', flexDirection: 'row', alignItems: 'flex-start' },
  recommendationRowSelected: { backgroundColor: '#FFF8F6' },
  checkbox: { width: 24, height: 24, borderRadius: 7, borderWidth: 1.5, borderColor: '#B7B0B9', alignItems: 'center', justifyContent: 'center', marginRight: 13, marginTop: 1 },
  checkboxSelected: { backgroundColor: '#FF6D5A', borderColor: '#FF6D5A' },
  recommendationCopy: { flex: 1, paddingRight: 4 },
  recommendationItemTitle: { color: '#29262D', fontSize: 15, lineHeight: 20, fontWeight: '700' },
  recommendationRationale: { color: '#756F79', fontSize: 13, lineHeight: 19, marginTop: 4 },
  redrawNotice: { backgroundColor: '#FFF0ED', borderRadius: 14, padding: 16, marginBottom: 28 },
  redrawNoticeTitle: { color: '#8F3E28', fontSize: 15, fontWeight: '800' },
  redrawNoticeText: { color: '#6F4B41', fontSize: 13, lineHeight: 20, marginTop: 6 },
  reviewActions: { gap: 10 },
  applyButton: { minHeight: 54, borderRadius: 14, backgroundColor: '#FF6D5A', paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  applyButtonDisabled: { backgroundColor: '#CFC8C2' },
  applyButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  skipButton: { minHeight: 50, borderRadius: 14, borderWidth: 1, borderColor: '#DDD8D3', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  skipButtonText: { color: '#29262D', fontSize: 14, fontWeight: '700' },
  redrawButton: { minHeight: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7 },
  redrawButtonText: { color: '#756F79', fontSize: 13, fontWeight: '600' },
});
