import { Platform } from 'react-native';
import { API_BASE_URL } from '@/constants/config';
import { ImageWorkflowJobStatus, ImageWorkflowResult, ImageWorkflowStage, ModelCatalog, Workflow, WorkflowRun, WorkflowSchedule, WorkflowScheduleInput, WorkflowSummary } from '@/types/workflow';
import { loadSettings } from '@/services/settings';

/** Append a file to FormData in a way that works on both native and web.
 * On native, RN's FormData accepts { uri, type, name }.
 * On web, we must fetch the URI and convert it to a real Blob. */
async function appendFile(
  form: FormData,
  fieldName: string,
  uri: string,
  mimeType: string,
  filename: string,
): Promise<void> {
  if (Platform.OS === 'web') {
    const response = await fetch(uri);
    const blob = await response.blob();
    form.append(fieldName, new File([blob], filename, { type: mimeType }));
  } else {
    form.append(fieldName, { uri, type: mimeType, name: filename } as any);
  }
}

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/$/, '');
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async applyGlobalModel(workflow: Workflow): Promise<Workflow> {
    const { globalModel } = await loadSettings();
    if (!globalModel) return workflow;
    return {
      ...workflow,
      nodes: workflow.nodes.map((node) =>
        node.model_override ? node : { ...node, model: globalModel }
      ),
    };
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const settings = await loadSettings();
    const url = `${settings.backendUrl || this.baseUrl}${endpoint}`;
    // When sending FormData, the browser MUST auto-generate Content-Type (with boundary).
    // Manually setting it — even just Accept — can cause multipart parsing to fail.
    const isFormData = options.body instanceof FormData;
    try {
      const providerHeaders: Record<string, string> = {};
      if (settings.globalModel) providerHeaders['X-Nodara-LLM-Model'] = settings.globalModel;
      if (settings.useCustomProvider) {
        if (settings.apiKey) providerHeaders['X-Nodara-LLM-Key'] = settings.apiKey;
        if (settings.providerBaseUrl) providerHeaders['X-Nodara-LLM-URL'] = settings.providerBaseUrl;
      }
      const response = await fetch(url, {
        ...options,
        headers: isFormData
          ? { 'Accept': 'application/json', ...providerHeaders }
          : {
              'Accept': 'application/json',
              ...providerHeaders,
              ...options.headers,
            },
      });

      if (!response.ok) {
        let errorMessage = `Server error (${response.status})`;
        try {
          const errData = await response.json();
          if (errData?.error?.message) {
            errorMessage = errData.error.message;
          } else if (errData?.detail) {
            errorMessage = typeof errData.detail === 'string'
              ? errData.detail
              : JSON.stringify(errData.detail);
          }
        } catch {
          // ignore json parse error
        }
        throw new Error(errorMessage);
      }

      return (await response.json()) as T;
    } catch (err: any) {
      if (err.message === 'Network request failed') {
        throw new Error(`Could not connect to backend at ${settings.backendUrl || this.baseUrl}. Check the URL and network.`);
      }
      throw err;
    }
  }


  async checkHealth(): Promise<boolean> {
    try {
      const res = await this.request<{ status: string }>('/health');
      return res.status === 'ok';
    } catch {
      return false;
    }
  }

  async getModels(): Promise<ModelCatalog> {
    return await this.request<ModelCatalog>('/api/models');
  }

  async getDemoWorkflow(): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>('/api/demo/workflow');
    return await this.applyGlobalModel(res.workflow);
  }

  async getDemoImageUrl(): Promise<string> {
    const settings = await loadSettings();
    return `${settings.backendUrl || this.baseUrl}/api/demo/example-image`;
  }

  async createFromText(text: string): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>('/api/workflows/from-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    return await this.applyGlobalModel(res.workflow);
  }

  async createFromVoice(audioUri: string): Promise<{ transcription: string; workflow: Workflow }> {
    const formData = new FormData();
    const response = await this.request<{ transcription: string; workflow: Workflow }>('/api/workflows/from-audio', {
      method: 'POST',
      body: formData,
    });
    return { ...response, workflow: await this.applyGlobalModel(response.workflow) };
  }

  async createFromImage(imageUri: string, mimeType?: string): Promise<ImageWorkflowResult> {
    // Detect MIME type from URI extension (iOS often returns .heic)
    const ext = imageUri.split('.').pop()?.toLowerCase() ?? 'jpg';
    const mimeMap: Record<string, string> = {
      jpg: 'image/jpeg',
      jpeg: 'image/jpeg',
      png: 'image/png',
      heic: 'image/heic',
      heif: 'image/heif',
      webp: 'image/webp',
    };
    const resolvedMime = mimeType || mimeMap[ext] || 'image/jpeg';
    const resolvedName = `diagram.${ext}`;

    const formData = new FormData();
    await appendFile(formData, 'image', imageUri, resolvedMime, resolvedName);

    const res = await this.request<ImageWorkflowResult>('/api/workflows/from-image', {
      method: 'POST',
      body: formData,
    });
    return { ...res, workflow: await this.applyGlobalModel(res.workflow) };
  }

  async createFromImageWithProgress(
    imageUri: string,
    mimeType: string | undefined,
    onProgress: (stage: ImageWorkflowStage) => void,
  ): Promise<ImageWorkflowResult> {
    const ext = imageUri.split('.').pop()?.toLowerCase() ?? 'jpg';
    const mimeMap: Record<string, string> = {
      jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', heic: 'image/heic',
      heif: 'image/heif', webp: 'image/webp',
    };
    const resolvedMime = mimeType || mimeMap[ext] || 'image/jpeg';
    const formData = new FormData();
    await appendFile(formData, 'image', imageUri, resolvedMime, `diagram.${ext}`);

    onProgress('queued');
    const created = await this.request<{ job_id: string }>('/api/workflows/from-image/jobs', {
      method: 'POST',
      body: formData,
    });

    const deadline = Date.now() + 5 * 60 * 1000;
    while (Date.now() < deadline) {
      const job = await this.request<ImageWorkflowJobStatus>(`/api/workflows/from-image/jobs/${created.job_id}`);
      onProgress(job.stage);
      if (job.status === 'failed') throw new Error(job.error || 'Could not read this workflow diagram.');
      if (job.status === 'completed' && job.result) {
        return { ...job.result, workflow: await this.applyGlobalModel(job.result.workflow) };
      }
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    throw new Error('Diagram processing took too long. Please try again.');
  }

  async listWorkflows(): Promise<WorkflowSummary[]> {
    const res = await this.request<{ workflows: WorkflowSummary[] }>('/api/workflows');
    return res.workflows;
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>(`/api/workflows/${id}`);
    return await this.applyGlobalModel(res.workflow);
  }

  async updateWorkflow(workflow: Workflow): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>(`/api/workflows/${workflow.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(workflow),
    });
    return res.workflow;
  }

  async setWorkflowEnabled(workflowId: string, enabled: boolean): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>(`/api/workflows/${workflowId}/enabled`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    return res.workflow;
  }

  async renameWorkflow(workflowId: string, name: string): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>(`/api/workflows/${workflowId}/name`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return res.workflow;
  }

  async getWorkflowSchedule(workflowId: string): Promise<WorkflowSchedule | null> {
    return await this.request<WorkflowSchedule | null>(`/api/workflows/${workflowId}/schedule`);
  }

  async saveWorkflowSchedule(workflowId: string, schedule: WorkflowScheduleInput): Promise<WorkflowSchedule> {
    return await this.request<WorkflowSchedule>(`/api/workflows/${workflowId}/schedule`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(schedule),
    });
  }

  async deleteWorkflowSchedule(workflowId: string): Promise<void> {
    await this.request<{ ok: boolean }>(`/api/workflows/${workflowId}/schedule`, { method: 'DELETE' });
  }

  async applyModelToAllWorkflows(model: string): Promise<void> {
    const workflows = await this.listWorkflows();
    for (const summary of workflows) {
      const workflow = await this.getWorkflow(summary.id);
      await this.updateWorkflow({
        ...workflow,
        nodes: workflow.nodes.map((node) =>
          node.model_override ? node : { ...node, model }
        ),
      });
    }
  }

  async deleteWorkflow(id: string): Promise<boolean> {
    const res = await this.request<{ ok: boolean }>(`/api/workflows/${id}`, {
      method: 'DELETE',
    });
    return res.ok;
  }

  async aiEditWorkflow(workflowId: string, instruction: string): Promise<Workflow> {
    const res = await this.request<{ workflow: Workflow }>(`/api/workflows/${workflowId}/ai-edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    });
    return res.workflow;
  }

  async generateAgentInstructions(workflowId: string, nodeId: string, userHint: string = ''): Promise<string> {
    const res = await this.request<{ instructions: string }>(
      `/api/workflows/${workflowId}/nodes/${nodeId}/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_hint: userHint }),
      }
    );
    return res.instructions;
  }

  async improveAgentInstructions(
    workflowId: string,
    nodeId: string,
    currentInstructions: string,
    userFeedback: string = ''
  ): Promise<string> {
    const res = await this.request<{ instructions: string }>(
      `/api/workflows/${workflowId}/nodes/${nodeId}/improve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_instructions: currentInstructions,
          user_feedback: userFeedback,
        }),
      }
    );
    return res.instructions;
  }

  async audioEditAgent(workflowId: string, nodeId: string, audioUri: string): Promise<string> {
    const formData = new FormData();
    await appendFile(formData, 'audio', audioUri, 'audio/m4a', 'agent_edit.m4a');

    const res = await this.request<{ instructions: string }>(
      `/api/workflows/${workflowId}/nodes/${nodeId}/audio-edit`,
      {
        method: 'POST',
        body: formData,
      }
    );
    return res.instructions;
  }

  async runWorkflow(workflowId: string, input: string): Promise<WorkflowRun> {
    const effectiveWorkflow = await this.getWorkflow(workflowId);
    await this.updateWorkflow(effectiveWorkflow);
    return await this.request<WorkflowRun>(`/api/workflows/${workflowId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input }),
    });
  }

  async getRunStatus(runId: string): Promise<WorkflowRun> {
    return await this.request<WorkflowRun>(`/api/runs/${runId}`);
  }

  async listWorkflowRuns(workflowId: string): Promise<WorkflowRun[]> {
    const response = await this.request<{ runs: WorkflowRun[] }>(`/api/workflows/${workflowId}/runs`);
    return response.runs;
  }

  async getRunReportUrl(runId: string): Promise<string> {
    const settings = await loadSettings();
    return `${settings.backendUrl || this.baseUrl}/api/runs/${runId}/report.pdf`;
  }

  async getWorkflowRunsReportUrl(workflowId: string): Promise<string> {
    const settings = await loadSettings();
    return `${settings.backendUrl || this.baseUrl}/api/workflows/${workflowId}/runs/report.pdf`;
  }

  /** Fetch n8n JSON export as a raw string (ready to write to file or share). */
  async exportToN8n(workflowId: string): Promise<string> {
    const settings = await loadSettings();
    const url = `${settings.backendUrl || this.baseUrl}/api/workflows/${workflowId}/export/n8n`;
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`Export failed (${response.status})`);
    }
    const json = await response.json();
    return JSON.stringify(json, null, 2);
  }
}

export const api = new ApiClient();
