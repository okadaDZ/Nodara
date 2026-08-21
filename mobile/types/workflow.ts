export interface Position {
  x: number;
  y: number;
}

export interface WorkflowNode {
  id: string;
  type: string;
  name: string;
  description: string;
  instructions: string;
  model?: string;
  model_override?: boolean;
  position?: Position | null;
}

export interface AvailableModel {
  id: string;
  name: string;
}

export interface ModelCatalog {
  default_model: string;
  models: AvailableModel[];
}

export interface WorkflowRecommendation {
  title: string;
  rationale: string;
  instruction: string;
}

export interface CreatorAnalysis {
  summary: string;
  confidence: number;
  requires_redraw: boolean;
  requires_user_decision: boolean;
  recommendations: WorkflowRecommendation[];
}

export interface ImageWorkflowResult {
  workflow: Workflow;
  analysis: CreatorAnalysis;
}

export type ImageWorkflowStage =
  | 'queued'
  | 'validate_image'
  | 'read_diagram'
  | 'build_graph'
  | 'review_structure'
  | 'validate_logic'
  | 'write_prompts'
  | 'review_prompts'
  | 'enhance_prompts'
  | 'finalize_workflow'
  | 'complete';

export interface ImageWorkflowJobStatus {
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  stage: ImageWorkflowStage;
  result?: ImageWorkflowResult | null;
  error?: string | null;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  kind?: 'flow' | 'conditional' | 'tool' | 'memory' | 'parser';
  label?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface WorkflowSummary {
  id: string;
  name: string;
  description: string;
  node_count: number;
  run_count: number;
  last_run_at?: string | null;
  enabled: boolean;
  schedule_enabled: boolean;
  schedule_mode?: 'once' | 'window' | null;
  next_run_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowSchedule {
  id: string;
  workflow_id: string;
  mode: 'once' | 'window';
  enabled: boolean;
  input_text: string;
  timezone: string;
  run_at?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  interval_minutes?: number | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_error?: string | null;
}

export type WorkflowScheduleInput = Omit<WorkflowSchedule, 'id' | 'workflow_id' | 'next_run_at' | 'last_run_at' | 'last_error'>;

export interface NodeRun {
  id: string;
  node_id: string;
  node_name: string;
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'skipped';
  input?: string | null;
  output?: string | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: 'running' | 'completed' | 'failed';
  input: string;
  final_output?: string | null;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
  nodes: NodeRun[];
}
