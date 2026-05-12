import type { ApiError, HumanReviewQueueResponse } from "./types";

const DEFAULT_GATEWAY_URL = "http://localhost:8000";

export const gatewayBaseUrl =
  import.meta.env.VITE_GATEWAY_API_URL?.replace(/\/$/, "") ?? DEFAULT_GATEWAY_URL;

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${gatewayBaseUrl}${path}`, {
    headers: {
      Accept: "application/json",
      "X-Correlation-ID": "operator-console-review-queue",
    },
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
