export class ApiError extends Error {
  constructor(public status: number, message: string, public traceId?: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string; error?: { message?: string; trace_id?: string } } | null;
    const traceId = payload?.error?.trace_id ?? response.headers.get("X-Trace-ID") ?? undefined;
    throw new ApiError(response.status, payload?.error?.message ?? payload?.detail ?? `请求失败 (${response.status})`, traceId);
  }
  return response.json() as Promise<T>;
}

export function queryString(values: object): string {
  const params = new URLSearchParams();
  Object.entries(values as Record<string, string | number | boolean | null | undefined>).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  });
  const result = params.toString();
  return result ? `?${result}` : "";
}
