const API_PREFIX = "/api/v1";

import { getAuthToken } from "./auth";

export interface HealthResponse {
  status: string;
}

export interface DocumentResponse {
  id: string;
  title: string;
  source_type: string;
  file_name: string | null;
  mime_type: string | null;
  project_id: string | null;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  project_id?: string | null;
  document_id?: string | null;
  source_type?: string | null;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface QueryRequest {
  query: string;
  top_k?: number;
  project_id?: string | null;
  document_id?: string | null;
  source_type?: string | null;
  temperature?: number;
}

export interface QueryChunk {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface QuerySource {
  citation_id: string;
  document_id: string;
  chunks: QueryChunk[];
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: QuerySource[];
  model: string;
  latency_ms: number;
  truncated: boolean;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getStatusMessage(status: number): string {
  switch (status) {
    case 401:
      return "Your session is no longer valid. Please sign in again.";

    case 403:
      return "You do not have permission to perform this action.";

    case 404:
      return "The requested resource was not found.";

    case 422:
      return "The request contains invalid data.";

    case 429:
      return "Too many requests. Please wait a moment and try again.";

    default:
      if (status >= 500) {
        return "PAIS is temporarily unavailable. Please try again.";
      }

      return `Request failed with status ${status}.`;
  }
}

async function getApiErrorMessage(
  response: Response,
): Promise<string> {
  const fallbackMessage = getStatusMessage(response.status);

  try {
    const body = (await response.json()) as {
      detail?: unknown;
    };

    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }

    if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null &&
            "msg" in item &&
            typeof item.msg === "string"
          ) {
            return item.msg;
          }

          return JSON.stringify(item);
        })
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join("; ");
      }
    }

    if (body.detail !== undefined) {
      return JSON.stringify(body.detail);
    }
  } catch {
    // Use the status-based fallback when the response is not JSON.
  }

  return fallbackMessage;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAuthToken();

  const headers = new Headers(options.headers);

  if (
    !headers.has("Content-Type") &&
    options.body &&
    !(options.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    throw new ApiError(
      0,
      "Unable to reach the PAIS API. Check that the backend is running and try again.",
    );
  }

  if (!response.ok) {
    const message = await getApiErrorMessage(response);

    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function uploadDocument(
  file: File,
  title: string,
  sourceType: string,
  projectId?: string,
): Promise<DocumentResponse> {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("title", title);
  formData.append("source_type", sourceType);

  if (projectId) {
    formData.append("project_id", projectId);
  }

  return request<DocumentResponse>("/documents", {
    method: "POST",
    body: formData,
  });
}

export async function searchDocuments(
  requestData: SearchRequest,
): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(requestData),
  });
}

export async function queryDocuments(
  requestData: QueryRequest,
): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify(requestData),
  });
}

export interface DailyResponse {
  day: string;
  timezone_name: string;
  summary: string;
  priorities: string[];
  decisions: string[];
  changes: string[];
  risks: string[];
  model: string | null;
  latency_ms: number | null;
}

export interface DailyRequest {
  day: string;
  timezone_name: string;
}

export async function getDaily(
  requestData: DailyRequest,
  signal?: AbortSignal,
): Promise<DailyResponse> {
  const params = new URLSearchParams({
    day: requestData.day,
    timezone_name: requestData.timezone_name,
  });

  return request<DailyResponse>(`/daily?${params.toString()}`, {
    signal,
  });
}

export interface IntelligenceTask {
  id: string;
  project_id: string | null;
  commitment_id: string | null;
  description: string;
  owner: string | null;
  due_at: string | null;
  priority: string | null;
  status: string;
  source_chunk_ids: string[];
}

export interface IntelligenceCommitment {
  id: string;
  project_id: string | null;
  description: string;
  owner: string | null;
  deadline_at: string | null;
  status: string;
  source_chunk_ids: string[];
}

export interface IntelligenceDecision {
  id: string;
  project_id: string | null;
  title: string;
  description: string;
  decision_date: string | null;
  status: string;
  source_chunk_ids: string[];
}

export interface IntelligenceProject {
  id: string;
  name: string;
  description: string | null;
  status: string;
  source_chunk_ids: string[];
}

export interface IntelligencePerson {
  id: string;
  name: string;
  email: string | null;
  source_chunk_ids: string[];
}

export interface IntelligenceRisk {
  id: string;
  title: string;
  description: string | null;
  severity: string | null;
  source_chunk_ids: string[];
}

export interface IntelligenceResponse {
  tasks: IntelligenceTask[];
  commitments: IntelligenceCommitment[];
  decisions: IntelligenceDecision[];
  projects: IntelligenceProject[];
  people: IntelligencePerson[];
  risks: IntelligenceRisk[];
}

export async function getIntelligence(
  signal?: AbortSignal,
): Promise<IntelligenceResponse> {
  return request<IntelligenceResponse>("/intelligence", {
    signal,
  });
}