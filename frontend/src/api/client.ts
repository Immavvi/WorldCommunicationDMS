const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
  }
}

export type Role = { name: "SUPER-ADMIN" | "ADMIN" };

export type User = {
  id: string;
  email: string;
  display_name?: string | null;
  is_active: boolean;
  must_change_password?: boolean;
  last_login_at?: string | null;
  created_at?: string;
  roles: Role[];
};

export type HealthStatus = { status: string; service: string };

type RequestOptions = RequestInit & { token?: string };

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, headers, ...requestOptions } = options;
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...requestOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as
      | { error?: { code?: string; message?: string } }
      | undefined;
    throw new ApiError(
      body?.error?.message ?? "The request could not be completed.",
      response.status,
      body?.error?.code,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function getHealthStatus(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>("/health");
}
