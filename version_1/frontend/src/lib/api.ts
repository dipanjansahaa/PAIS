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

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);

    this.name = "ApiError";
    this.status = status;
  }
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

  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const body = (await response.json()) as {
        detail?: string;
      };

      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the default HTTP error message.
    }

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