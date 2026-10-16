export class ApiError extends Error {
  constructor(message: string, public status: number, public details?: unknown) { super(message); }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, cache: "no-store" });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = result?.detail;
    throw new ApiError(typeof detail === "string" ? detail :
      result?.errors?.join(" · ") || (Array.isArray(detail) ? "Check the supplied fields and try again." : "The request could not be completed."), response.status, result);
  }
  return result as T;
}

export const emptyEvidence = { nodes: [], edges: [], paths: [], truncated: false };
export const date = (value: string | null, options?: Intl.DateTimeFormatOptions) => value
  ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", ...options }).format(new Date(value)) : "Not recorded";
export const shortId = (id: string) => id.split(":").slice(1).join(":");
export const initials = (name: string) => name.split(" ").map(n => n[0]).slice(0, 2).join("");
