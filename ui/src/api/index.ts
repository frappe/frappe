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
export {
  attachFile,
  downloadFile,
  removeAttachment,
  uploadFile,
  DEFAULT_CHUNK_SIZE,
  type Attachment,
  type AttachmentsPart,
  type FileDocument,
  type UploadFields,
  type UploadOptions,
} from "./upload";

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

export interface SessionUser {
  name: string;
  full_name: string;
  email: string;
  user_image: string | null;
}

/** The signed-in person and the site settings a client renders for them. */
export interface Session {
  user: SessionUser;
  roles: string[];
  lang: string;
  timezone: string;
  defaults: Record<string, unknown>;
}

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
  /** The function returns nothing, so `data` is `null`. */
  nullable?: boolean;
}

export type NullableMethodOptions = MethodOptions & { nullable: true };

export function runMethod<T = unknown>(
  method: string,
  args: Args | undefined,
  options: NullableMethodOptions
): Promise<Envelope<T | null>>;
export function runMethod<T = unknown>(
  method: string,
  args?: Args,
  options?: MethodOptions
): Promise<Envelope<T>>;
export function runMethod<T = unknown>(
  method: string,
  args: Args = {},
  { http = "POST", signal, nullable }: MethodOptions = {}
): Promise<Envelope<T | null>> {
  const path = `/method/${segment(method)}`;
  if (http === "GET") return request<T>("GET", path, { query: args, signal, nullable });
  return request<T>("POST", path, { body: args, signal, nullable });
}

export function runDocumentMethod<T = unknown>(
  doctype: string,
  name: string,
  method: string,
  args: Args | undefined,
  options: NullableMethodOptions
): Promise<Envelope<T | null>>;
export function runDocumentMethod<T = unknown>(
  doctype: string,
  name: string,
  method: string,
  args?: Args,
  options?: MethodOptions
): Promise<Envelope<T>>;
export function runDocumentMethod<T = unknown>(
  doctype: string,
  name: string,
  method: string,
  args: Args = {},
  { http = "POST", signal, nullable }: MethodOptions = {}
): Promise<Envelope<T | null>> {
  const path = `${documentPath(doctype, name)}/method/${segment(method)}`;
  if (http === "GET") return request<T>("GET", path, { query: args, signal, nullable });
  return request<T>("POST", path, { body: args, signal, nullable });
}

/** A read beside the document, `GET /document/<doctype>/<name>/<part>`, such as `activity`. */
export function getDocumentPart<T = unknown>(
  doctype: string,
  name: string,
  part: string,
  params: Query = {},
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("GET", `${documentPath(doctype, name)}/${segment(part)}`, {
    query: params,
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

/** A Guest gets a Guest session rather than a refusal, so this never has to be guarded. */
export function getSession({ signal }: CallOptions = {}): Promise<Envelope<Session>> {
  return request<Session>("GET", "/session", { signal });
}

export function logout({ signal }: CallOptions = {}): Promise<Envelope<null>> {
  return request<null>("POST", "/method/logout", { signal, nullable: true });
}

/** Cached server-side for a year: `version` is the only thing that invalidates it. */
export function getTranslations(
  lang: string,
  version: string,
  { signal }: CallOptions = {}
): Promise<Envelope<Record<string, string>>> {
  return request<Record<string, string>>("GET", "/method/frappe.translate.get_boot_translations", {
    query: { lang, v: version },
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

export type CollabPart =
  | "assignments"
  | "shares"
  | "tags"
  | "favourites"
  | "follows"
  | "comments";

export interface Assignment {
  user: string;
  description?: string;
  priority?: string;
  date?: string;
}
export interface Share {
  user: string;
  read?: 0 | 1;
  write?: 0 | 1;
  submit?: 0 | 1;
  share?: 0 | 1;
}
export interface Favourite {
  user: string;
  creation?: string;
}
export interface Comment {
  name: string;
  creation?: string;
  content: string;
  owner: string;
  comment_type?: string;
}
export type Users = Record<string, { full_name?: string; user_image?: string }>;

/** A collaboration write's answer: the refreshed part under its own key, and the people it names. */
export type PartResponse<P extends CollabPart, T> = { [K in P]: T } & { users?: Users };

export function addPart<T>(
  doctype: string,
  name: string,
  part: CollabPart,
  body?: unknown,
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("POST", partPath(doctype, name, part), { body, signal });
}

export function removePart<T>(
  doctype: string,
  name: string,
  part: CollabPart,
  key?: string,
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("DELETE", partPath(doctype, name, part, key), { signal });
}

export function updatePart<T>(
  doctype: string,
  name: string,
  part: CollabPart,
  key: string,
  body: unknown,
  { signal }: CallOptions = {}
): Promise<Envelope<T>> {
  return request<T>("PATCH", partPath(doctype, name, part, key), { body, signal });
}

export function addAssignment(
  doctype: string,
  name: string,
  assignment: Assignment,
  options?: CallOptions
) {
  return addPart<PartResponse<"assignments", Assignment[]>>(
    doctype, name, "assignments", assignment, options
  );
}

export function removeAssignment(
  doctype: string,
  name: string,
  user: string,
  options?: CallOptions
) {
  return removePart<PartResponse<"assignments", Assignment[]>>(
    doctype, name, "assignments", user, options
  );
}

export function addShare(doctype: string, name: string, share: Share, options?: CallOptions) {
  return addPart<PartResponse<"shares", Share[]>>(doctype, name, "shares", share, options);
}

/** `user` is the string "everyone" for the everyone share. */
export function removeShare(doctype: string, name: string, user: string, options?: CallOptions) {
  return removePart<PartResponse<"shares", Share[]>>(doctype, name, "shares", user, options);
}

export function addTag(doctype: string, name: string, tag: string, options?: CallOptions) {
  return addPart<PartResponse<"tags", string[]>>(doctype, name, "tags", { tag }, options);
}

export function removeTag(doctype: string, name: string, tag: string, options?: CallOptions) {
  return removePart<PartResponse<"tags", string[]>>(doctype, name, "tags", tag, options);
}

export function addFavourite(doctype: string, name: string, options?: CallOptions) {
  return addPart<PartResponse<"favourites", Favourite[]>>(
    doctype, name, "favourites", undefined, options
  );
}

export function removeFavourite(doctype: string, name: string, options?: CallOptions) {
  return removePart<PartResponse<"favourites", Favourite[]>>(
    doctype, name, "favourites", undefined, options
  );
}

export function addFollow(doctype: string, name: string, options?: CallOptions) {
  return addPart<PartResponse<"follows", boolean>>(doctype, name, "follows", undefined, options);
}

export function removeFollow(doctype: string, name: string, options?: CallOptions) {
  return removePart<PartResponse<"follows", boolean>>(
    doctype, name, "follows", undefined, options
  );
}

export function addComment(doctype: string, name: string, content: string, options?: CallOptions) {
  return addPart<PartResponse<"comments", Comment[]>>(
    doctype, name, "comments", { content }, options
  );
}

export function updateComment(
  doctype: string,
  name: string,
  comment: string,
  content: string,
  options?: CallOptions
) {
  return updatePart<PartResponse<"comments", Comment[]>>(
    doctype, name, "comments", comment, { content }, options
  );
}

export function removeComment(
  doctype: string,
  name: string,
  comment: string,
  options?: CallOptions
) {
  return removePart<PartResponse<"comments", Comment[]>>(
    doctype, name, "comments", comment, options
  );
}

function partPath(doctype: string, name: string, part: CollabPart, key?: string): string {
  const base = `${documentPath(doctype, name)}/${part}`;
  return key === undefined ? base : `${base}/${segment(key)}`;
}
