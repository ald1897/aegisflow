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

export interface ApiError {
  error: string;
  message: string;
  correlation_id?: string | null;
}
