import type {
  CodingBenchmarkRequest,
  CodingBenchmarkResponse,
  CodingTaskMetadata,
} from "@/lib/types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach the AgentBench API.", 0);
  }

  if (!response.ok) {
    let message = `AgentBench API request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) {
        message = body.detail;
      }
    } catch {
      // Keep the concise status-based message for non-JSON errors.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getCodingTasks(): Promise<CodingTaskMetadata[]> {
  return request<CodingTaskMetadata[]>("/api/coding/tasks");
}

export function getCodingTask(taskId: string): Promise<CodingTaskMetadata> {
  return request<CodingTaskMetadata>(
    `/api/coding/tasks/${encodeURIComponent(taskId)}`,
  );
}

export function runCodingBenchmark(
  payload: CodingBenchmarkRequest,
): Promise<CodingBenchmarkResponse> {
  return request<CodingBenchmarkResponse>("/api/coding/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
