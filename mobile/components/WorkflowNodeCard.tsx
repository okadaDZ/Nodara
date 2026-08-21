import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { WorkflowNode } from '@/types/workflow';
import { Bot, ChevronRight, Sparkles, Trash2 } from 'lucide-react-native';

interface WorkflowNodeCardProps {
  node: WorkflowNode;
  index: number;
  onPress: () => void;
  onDelete?: () => void;
}

export const WorkflowNodeCard: React.FC<WorkflowNodeCardProps> = ({
  node,
  index,
  onPress,
  onDelete,
}) => {
  return (
    <TouchableOpacity activeOpacity={0.7} style={styles.card} onPress={onPress}>
      <View style={styles.headerRow}>
        <View style={styles.indexBadge}>
          <Text style={styles.indexText}>{index + 1}</Text>
        </View>
        <View style={styles.titleContainer}>
          <Text style={styles.title} numberOfLines={1}>
            {node.name || `Agent ${index + 1}`}
          </Text>
          <Text style={styles.description} numberOfLines={2}>
            {node.description || 'Tap to configure agent responsibilities'}
          </Text>
        </View>
        <View style={styles.actions}>
          {onDelete && (
            <TouchableOpacity
              onPress={onDelete}
              style={styles.deleteButton}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Trash2 size={16} color="#EF4444" />
            </TouchableOpacity>
          )}
          <ChevronRight size={18} color="#A59FA8" />
        </View>
      </View>

      {node.instructions ? (
        <View style={styles.instructionPill}>
          <Sparkles size={12} color="#7563E8" />
          <Text style={styles.instructionText} numberOfLines={1}>
            Instructions configured
          </Text>
        </View>
      ) : (
        <View style={[styles.instructionPill, styles.warningPill]}>
          <Text style={styles.warningText}>No instructions yet</Text>
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  indexBadge: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#EFEDFF',
    borderWidth: 1,
    borderColor: '#CFC9FA',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  indexText: {
    color: '#7563E8',
    fontSize: 14,
    fontWeight: '700',
  },
  titleContainer: {
    flex: 1,
    marginRight: 8,
  },
  title: {
    color: '#29262D',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 2,
  },
  description: {
    color: '#756F79',
    fontSize: 13,
    lineHeight: 18,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  deleteButton: {
    padding: 6,
    borderRadius: 8,
    backgroundColor: '#FFF0ED',
  },
  instructionPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F4F1FF',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    marginTop: 12,
    alignSelf: 'flex-start',
    gap: 6,
    borderWidth: 1,
    borderColor: '#DED9FF',
  },
  instructionText: {
    color: '#6553CF',
    fontSize: 12,
    fontWeight: '500',
  },
  warningPill: {
    borderColor: '#F3D49E',
    backgroundColor: '#FFF8E8',
  },
  warningText: {
    color: '#9A6817',
    fontSize: 12,
    fontWeight: '500',
  },
});
