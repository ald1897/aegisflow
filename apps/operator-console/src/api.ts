import type {
  ApiError,
  ApprovalDecisionRequest,
  ApprovalDecisionResponse,
  HumanReviewQueueResponse,
  WorkflowRecoveryActionsResponse,
  WorkflowReplayRunsResponse,
  WorkflowReviewContext,
} from "./types";

const DEFAULT_GATEWAY_URL = "http://localhost:8000";

export const gatewayBaseUrl =
  import.meta.env.VITE_GATEWAY_API_URL?.replace(/\/$/, "") ?? DEFAULT_GATEWAY_URL;

interface RequestOptions {
  method?: "GET" | "POST";
  actorId?: string;
  body?: unknown;
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Correlation-ID": "operator-console-review",
  };

  if (options.actorId) {
    headers["X-Actor-ID"] = options.actorId;
  }

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${gatewayBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    let detail: ApiError | undefined;
    try {
      detail = (await response.json()) as ApiError;
    } catch {
      detail = undefined;
    }
    throw new Error(detail?.message ?? `Gateway request failed with HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getHumanReviewQueue(): Promise<HumanReviewQueueResponse> {
  return requestJson<HumanReviewQueueResponse>("/api/v1/reviews/human-review-queue");
}

export async function getWorkflowReviewContext(workflowId: string): Promise<WorkflowReviewContext> {
  return requestJson<WorkflowReviewContext>(`/api/v1/workflows/${workflowId}/review-context`);
}

export async function getWorkflowReplayRuns(workflowId: string): Promise<WorkflowReplayRunsResponse> {
  return requestJson<WorkflowReplayRunsResponse>(`/api/v1/workflows/${workflowId}/replay-runs`);
}

export async function getWorkflowRecoveryActions(workflowId: string): Promise<WorkflowRecoveryActionsResponse> {
  return requestJson<WorkflowRecoveryActionsResponse>(`/api/v1/workflows/${workflowId}/recovery-actions`);
}

export async function submitApprovalDecision(
  workflowId: string,
  actorId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalDecisionResponse> {
  return requestJson<ApprovalDecisionResponse>(`/api/v1/workflows/${workflowId}/approvals`, {
    method: "POST",
    actorId,
    body: payload,
  });
}
