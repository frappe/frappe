/**
 * The one place the desk talks to the server: every request goes to
 * `/api/v2`, and a later change of transport touches this folder only.
 */
import { request, type Query } from "./request";
import { ApiError, type Envelope } from "./envelope";

export {
  ApiError,
  isApiError,
  readEnvelope,
  TIMESTAMP_MISMATCH,
  type Envelope,
  type ErrorEntry,
} from "./envelope";
export { apiUrl, request, requestHeaders, type HttpMethod, type Query } from "./request";

export type DocumentRecord = Record<string, unknown> & { name: string; modified?: string };
export type Args = Record<string, unknown>;

export interface CallOptions {
  signal?: AbortSignal;
}

export interface IncludeOptions extends CallOptions {
  /** Named parts the server returns beside `data`, one key each; a string is sent as it is. */
  include?: readonly string[] | string;
}

/** The list route's query, passed through by name; `filters` and `or_filters` are opaque JSON. */
export interface ListQuery extends Query {
  fields?: readonly string[];
  filters?: unknown;
  or_filters?: unknown;
  order_by?: string;
  start?: number;
  limit?: number;
  group_by?: string;
}

/** The list route's response; `count` is `null` when the server gave up counting in time. */
export type ListEnvelope<T> = Envelope<T[]> & {
  has_next_page: boolean;
  count?: number | null;
  count_capped?: boolean;
};

export interface CountQuery extends Query {
  filters?: unknown;
  or_filters?: unknown;
  distinct?: boolean;
}

export interface SearchQuery extends Query {
  txt: string;
  filters?: unknown;
  reference_doctype?: string;
  query?: string;
  limit?: number;
  start?: number;
}

export interface SearchResult {
  value: string;
  label?: string;
  description?: string;
}

export const UPLOAD_PATH = "/method/upload_file";

export function getDocument<T extends DocumentRecord = DocumentRecord>(
  doctype: string,
  name: string,
  { include, signal }: IncludeOptions = {}
): Promise<Envelope<T>> {
  return request<T>("GET", documentPath(doctype, name), {
    query: { include: joinInclude(include) },
    signal,
  });
}

export function listDocuments<T = DocumentRecord>(
  doctype: string,
  query: ListQuery = {},
  { include, signal }: IncludeOptions = {}
): Promise<ListEnvelope<T>> {
  return request<T[]>("GET", `/document/${segment(doctype)}`, {
    query: { ...query, include: joinInclude(include) },
    signal,
  }) as Promise<ListEnvelope<T>>;
}

export function countDocuments(
  doctype: string,
  query: CountQuery = {},
  { signal }: CallOptions = {}
): Promise<Envelope<number | null>> {
  return request<number | null>("GET", `/doctype/${segment(doctype)}/count`, { query, signal });
}

export function searchDocuments(
  doctype: string,
  query: SearchQuery,
  { signal }: CallOptions = {}
): Promise<Envelope<SearchResult[]>> {
  return request<SearchResult[]>("GET", `/doctype/${segment(doctype)}/search`, { query, signal });
}

export function createDocument<T extends DocumentRecord = DocumentRecord>(
  doctype: string,
  doc: Partial<T>,
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("POST", `/document/${segment(doctype)}`, { body: doc, signal });
}

/** Save the whole document; without `modified` the server cannot refuse a save over someone else's. */
export function updateDocument<T extends DocumentRecord = DocumentRecord>(
  doctype: string,
  name: string,
  doc: T,
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  if (!doc.modified) {
    return Promise.reject(
      new ApiError(
        { type: "MissingModified", message: `${doctype} ${name}: the document has no "modified" value` },
        0
      )
    );
  }
  return request<T>("PATCH", documentPath(doctype, name), { body: doc, signal });
}

export function deleteDocument(
  doctype: string,
  name: string,
  { signal }: CallOptions = {}
): Promise<Envelope<"ok">> {
  return request<"ok">("DELETE", documentPath(doctype, name), { signal });
}

export function copyDocument<T extends DocumentRecord = DocumentRecord>(
  doctype: string,
  name: string,
  { signal }: CallOptions = {}
): Promise<Envelope<Partial<T>>> {
  return request<Partial<T>>("GET", `${documentPath(doctype, name)}/copy`, { signal });
}

export interface MethodOptions extends CallOptions {
  /** `GET` for a read the browser may cache; the default `POST` for everything else. */
  http?: "GET" | "POST";
}

export function runMethod<T = unknown>(
  method: string,
  args: Args = {},
  { http = "POST", signal }: MethodOptions = {}
): Promise<Envelope<T>> {
  const path = `/method/${segment(method)}`;
  if (http === "GET") return request<T>("GET", path, { query: args, signal });
  return request<T>("POST", path, { body: args, signal });
}

export function runDocumentMethod<T = unknown>(
  doctype: string,
  name: string,
  method: string,
  args: Args = {},
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("POST", `${documentPath(doctype, name)}/method/${segment(method)}`, {
    body: args,
    signal,
  });
}

export function getMeta<T = Record<string, unknown>>(
  doctype: string,
  { include, signal }: IncludeOptions = {}
): Promise<Envelope<T>> {
  return request<T>("GET", `/doctype/${segment(doctype)}/meta`, {
    query: { include: joinInclude(include) },
    signal,
  });
}

function documentPath(doctype: string, name: string): string {
  return `/document/${segment(doctype)}/${segment(name)}`;
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function joinInclude(include?: readonly string[] | string): string | undefined {
  if (typeof include === "string") return include || undefined;
  return include?.length ? include.join(",") : undefined;
}
