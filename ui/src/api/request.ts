import { ApiError, readEnvelope, type Envelope, type ReadOptions } from "./envelope";

const BASE = "/api/v2";

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
export type Query = Record<string, unknown>;

export interface RequestOptions extends Pick<ReadOptions, "nullable"> {
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
}

export function apiUrl(path: string, query?: Query): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null) continue;
    search.set(key, encodeQueryValue(value));
  }
  const encoded = search.toString();
  return encoded ? `${BASE}${path}?${encoded}` : `${BASE}${path}`;
}

/** The headers every request sends; the uploader shares them with its XHR. */
export function requestHeaders({ json = true } = {}): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json) headers["Content-Type"] = "application/json; charset=utf-8";
  const site = globalThis.location?.hostname;
  if (site) headers["X-Frappe-Site-Name"] = site;
  const token = (globalThis as { csrf_token?: string }).csrf_token;
  if (token && token !== "{{ csrf_token }}") headers["X-Frappe-CSRF-Token"] = token;
  return headers;
}

export async function request<T>(
  method: HttpMethod,
  path: string,
  { query, body, signal, nullable }: RequestOptions = {}
): Promise<Envelope<T>> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path, query), {
      method,
      headers: requestHeaders({ json: body !== undefined }),
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") throw error;
    throw new ApiError({ type: "NetworkError", message: String(error) }, 0);
  }
  return readEnvelope<T>(await parseBody(response), response.status, {
    source: `${method} ${path}`,
    nullable,
  });
}

// The server reads a query flag with `bool()`, so the string "false" must not reach it.
function encodeQueryValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "1" : "0";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
