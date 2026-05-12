export type WorkflowPriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export type WorkflowState =
  | "NEW"
  | "INTAKE_IN_PROGRESS"
  | "DOCUMENT_ANALYSIS_PENDING"
  | "RISK_REVIEW_PENDING"
  | "HUMAN_REVIEW_REQUIRED"
  | "APPROVED"
  | "REJECTED"
  | "COMPLETED"
  | "FAILED";

export interface HumanReviewQueueItem {
  workflow_id: string;
  workflow_type: string;
  state: WorkflowState;
  priority: WorkflowPriority;
  correlation_id: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface HumanReviewQueueResponse {
  items: HumanReviewQueueItem[];
  count: number;
}

export interface WorkflowRecord {
  workflow_id: string;
  workflow_type: string;
  state: WorkflowState;
  priority: WorkflowPriority;
  correlation_id: string;
  created_at: string;
  updated_at: string;
  temporal_workflow_id?: string | null;
  temporal_run_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface TimelineEntry {
  timeline_entry_id: string;
  workflow_id: string;
  entry_type: string;
  message: string;
  state?: WorkflowState | null;
  correlation_id: string;
  created_by: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AgentExecutionRecord {
  agent_execution_id: string;
  workflow_id: string;
  agent_id: string;
  prompt_id: string;
  prompt_version: string;
  model_name: string;
  status: string;
  validation_status: string;
  confidence_score: number;
  requires_human_review: boolean;
  output: Record<string, unknown>;
  metadata: Record<string, unknown>;
  correlation_id: string;
  created_by: string;
  started_at: string;
  completed_at?: string | null;
  created_at: string;
}

export interface ToolInvocationRecord {
  tool_invocation_id: string;
  workflow_id: string;
  agent_execution_id?: string | null;
  agent_id: string;
  tool_id: string;
  status: string;
  permission_status: string;
  input_validation_status: string;
  output_validation_status: string;
  input_metadata: Record<string, unknown>;
  output: Record<string, unknown>;
  metadata: Record<string, unknown>;
  error_message?: string | null;
  correlation_id: string;
  created_by: string;
  started_at: string;
  completed_at?: string | null;
  created_at: string;
}

export interface ApprovalRecord {
  approval_id: string;
  workflow_id: string;
  decision: ApprovalDecision;
  decision_reason: string;
  comment: string;
  reviewed_by: string;
  reviewed_at: string;
  metadata: Record<string, unknown>;
  correlation_id: string;
  created_at: string;
}

export interface WorkflowReviewContext {
  workflow: WorkflowRecord;
  timeline: TimelineEntry[];
  agent_executions: AgentExecutionRecord[];
  tool_invocations: ToolInvocationRecord[];
  approvals: ApprovalRecord[];
}

export type ApprovalDecision = "APPROVED" | "REJECTED";

export interface ApprovalDecisionRequest {
  decision: ApprovalDecision;
  decision_reason: string;
  comment: string;
  metadata?: Record<string, unknown>;
}

export interface ApprovalDecisionResponse {
  workflow: WorkflowRecord;
  approval: ApprovalRecord;
  decision_result: Record<string, unknown>;
}

export interface ApiError {
  error: string;
  message: string;
  correlation_id?: string | null;
}
