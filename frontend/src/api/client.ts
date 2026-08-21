const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type HealthStatus = { status: string; service: string };

export async function getHealthStatus(): Promise<HealthStatus> {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) {
    throw new Error("The API health check failed.");
  }
  return response.json() as Promise<HealthStatus>;
}
