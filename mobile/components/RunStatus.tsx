import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { NodeRun, WorkflowRun } from '@/types/workflow';
import { CheckCircle2, ChevronDown, ChevronUp, Clock, MinusCircle, XCircle } from 'lucide-react-native';

interface RunStatusProps {
  run: WorkflowRun;
}

export const RunStatus: React.FC<RunStatusProps> = ({ run }) => {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [nodeId]: !prev[nodeId],
    }));
  };

  const renderStatusIcon = (status: NodeRun['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={20} color="#2F9C72" />;
      case 'running':
        return <ActivityIndicator size="small" color="#FF6D5A" />;
      case 'failed':
        return <XCircle size={20} color="#C94D43" />;
      case 'skipped':
        return <MinusCircle size={19} color="#A59FA8" />;
      case 'waiting':
      default:
        return <Clock size={18} color="#A59FA8" />;
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Run progress</Text>
          <Text style={styles.progressMeta}>{run.nodes.filter((node) => node.status === 'completed').length} of {run.nodes.length} nodes complete</Text>
        </View>
        <View
          style={[
            styles.runStatusBadge,
            run.status === 'completed' && styles.completedBadge,
            run.status === 'failed' && styles.failedBadge,
            run.status === 'running' && styles.runningBadge,
          ]}
        >
          <Text
            style={[
              styles.runStatusText,
              run.status === 'completed' && styles.completedText,
              run.status === 'failed' && styles.failedText,
              run.status === 'running' && styles.runningText,
            ]}
          >
            {run.status.toUpperCase()}
          </Text>
        </View>
      </View>

      <View style={styles.nodeList}>
        {run.nodes.map((node, index) => {
          const isExpanded = expandedNodes[node.node_id];
          return (
            <View key={node.id} style={styles.nodeItem}>
              <TouchableOpacity
                activeOpacity={0.7}
                style={styles.nodeHeader}
                onPress={() => node.output && toggleExpand(node.node_id)}
                disabled={!node.output && !node.error}
              >
                <View style={styles.nodeLeft}>
                  <View style={styles.iconContainer}>{renderStatusIcon(node.status)}</View>
                  <View>
                    <Text style={styles.nodeName}>
                      {index + 1}. {node.node_name || `Agent ${index + 1}`}
                    </Text>
                    <Text style={styles.nodeStateText}>
                      {node.status === 'completed'
                        ? 'Completed'
                        : node.status === 'running'
                        ? 'Processing...'
                        : node.status === 'failed'
                        ? 'Failed'
                        : node.status === 'skipped'
                        ? 'Skipped by route'
                        : 'Waiting in queue'}
                    </Text>
                  </View>
                </View>

                {(node.output || node.error) && (
                  <View style={styles.expandAction}>
                    <Text style={styles.viewOutputText}>
                      {isExpanded ? 'Hide' : 'View'}
                    </Text>
                    {isExpanded ? (
                      <ChevronUp size={16} color="#B9502E" />
                    ) : (
                      <ChevronDown size={16} color="#B9502E" />
                    )}
                  </View>
                )}
              </TouchableOpacity>

              {isExpanded && (
                <View style={styles.outputBox}>
                  {node.output && (
                    <>
                      <Text style={styles.outputLabel}>Output</Text>
                      <Text style={styles.outputText}>{node.output}</Text>
                    </>
                  )}
                  {node.error && (
                    <>
                      <Text style={[styles.outputLabel, styles.errorLabel]}>Error details</Text>
                      <Text style={[styles.outputText, styles.errorText]}>{node.error}</Text>
                    </>
                  )}
                </View>
              )}
            </View>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#DDD8D3',
    marginVertical: 12,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#EEEAE7',
  },
  title: {
    color: '#29262D',
    fontSize: 16,
    fontWeight: '800',
  },
  progressMeta: { color: '#756F79', fontSize: 11, marginTop: 3 },
  runStatusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 99,
    backgroundColor: '#ECE9E5',
  },
  runningBadge: {
    backgroundColor: '#FFF0ED',
  },
  completedBadge: {
    backgroundColor: '#E9F5EF',
  },
  failedBadge: {
    backgroundColor: '#FBECEA',
  },
  runStatusText: {
    color: '#756F79',
    fontSize: 11,
    fontWeight: '700',
  },
  runningText: {
    color: '#B9502E',
  },
  completedText: {
    color: '#237A57',
  },
  failedText: {
    color: '#A63F36',
  },
  nodeList: {
    gap: 8,
  },
  nodeItem: {
    backgroundColor: '#FAF9F7',
    borderRadius: 12,
    padding: 13,
    borderWidth: 1,
    borderColor: '#E3DEDA',
  },
  nodeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  nodeLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  iconContainer: {
    width: 24,
    alignItems: 'center',
  },
  nodeName: {
    color: '#29262D',
    fontSize: 14,
    fontWeight: '600',
  },
  nodeStateText: {
    color: '#756F79',
    fontSize: 12,
    marginTop: 1,
  },
  expandAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewOutputText: {
    color: '#B9502E',
    fontSize: 12,
    fontWeight: '500',
  },
  outputBox: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E3DEDA',
  },
  outputLabel: {
    color: '#756F79',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  outputText: {
    color: '#3F3A42',
    fontSize: 13,
    lineHeight: 18,
    backgroundColor: '#FFFFFF',
    padding: 10,
    borderRadius: 8,
  },
  errorLabel: {
    color: '#A63F36',
  },
  errorText: {
    color: '#7F342D',
    backgroundColor: '#FBECEA',
  },
});
