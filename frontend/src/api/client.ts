/**
 * Client HTTP centralizzato per l'API JobMatcher.
 *
 * Il token viene letto da `VITE_API_TOKEN` (build-time). Fallback al valore
 * di dev locale per far girare il progetto out-of-the-box.
 */

const API_TOKEN =
  import.meta.env.VITE_API_TOKEN?.toString() ?? "local-dev-token-2026";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  json?: unknown;
  /** Upload multipart (es. CV in PDF) — niente Content-Type manuale, il
   * browser imposta da solo il boundary. */
  formData?: FormData;
  headers?: Record<string, string>;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = path.startsWith("/") ? path : `/${path}`;
  if (!query) return url;
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    search.append(k, String(v));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function api<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { json, formData, headers, query, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "X-API-Token": API_TOKEN,
    ...(headers ?? {}),
  };
  const init: RequestInit = { ...rest, headers: finalHeaders };

  if (json !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  } else if (formData !== undefined) {
    init.body = formData;
  }

  const response = await fetch(buildUrl(path, query), init);

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    const detail =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, body, detail);
  }

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}
