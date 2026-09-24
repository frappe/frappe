/**
 * Uploads and downloads: multipart on the v2 document routes, with progress and cancel.
 * A file larger than the chunk size goes in parts, and only the last part answers with it.
 */
import { takeTicket } from "../cache";
import { ApiError, readEnvelope, type Envelope } from "./envelope";
import { fed, fedAfter, feedPartReply } from "./feed";
import { apiUrl, requestHeaders } from "./request";
import type { Users } from "./index";

/** The server's own default; a desk that knows the site's `file_chunk_size` passes that. */
export const DEFAULT_CHUNK_SIZE = 25 * 1024 * 1024;

const FILE_PATH = "/document/File";

/** The File fields that ride beside the bytes; the server reads them from the form. */
export type UploadFields = Record<string, string | number | boolean | null | undefined>;

export interface UploadOptions {
  onProgress?: (loaded: number, total: number) => void;
  signal?: AbortSignal;
  /** Bytes per part; the site's `file_chunk_size`. */
  chunkSize?: number;
}

export interface FileDocument {
  name: string;
  file_name: string;
  file_url: string;
  is_private: 0 | 1;
  file_type?: string;
  file_size?: number;
}

/** One row of the `attachments` part, as the read and the writes return it. */
export interface Attachment {
  name: string;
  file_name: string;
  file_url: string;
  file_type?: string;
  file_size?: number;
  is_private: 0 | 1;
  attached_to_field?: string | null;
  folder?: string;
  creation: string;
  owner: string;
}

/** An attachment write's answer: the refreshed part, the people it names, and the new row. */
export interface AttachmentsPart {
  attachments: Attachment[];
  users?: Users;
  /** The File this upload created; a delete answers without it. */
  file?: string;
}

/** Upload a file that hangs on no record. */
export function uploadFile(
  file: File,
  fields: UploadFields = {},
  options: UploadOptions = {}
): Promise<Envelope<FileDocument>> {
  return uploadTo<FileDocument>(FILE_PATH, file, fields, options);
}

/** Upload a file and attach it to a record; answers with the refreshed `attachments` part. */
export function attachFile(
  doctype: string,
  name: string,
  file: File,
  fields: UploadFields = {},
  options: UploadOptions = {}
): Promise<Envelope<AttachmentsPart>> {
  const ticket = takeTicket();
  const path = attachmentsPath(doctype, name);
  const uploading = uploadTo<AttachmentsPart>(path, file, fields, options);
  return fedAfter(ticket, uploading, feedPartReply(doctype, name, "attachments"));
}

/** Delete an attached file; answers with the refreshed `attachments` part. */
export function removeAttachment(
  doctype: string,
  name: string,
  fileName: string,
  { signal }: { signal?: AbortSignal } = {}
): Promise<Envelope<AttachmentsPart>> {
  const path = attachmentsPath(doctype, name, fileName);
  const feed = feedPartReply(doctype, name, "attachments");
  return fed<AttachmentsPart>("DELETE", path, { signal }, feed);
}

/**
 * The bytes at a URL the server gave us: a `file_url`, or a v2 method route that streams a
 * file. The response is not an envelope, so a failure is read as one only when it fails.
 */
export async function downloadFile(
  url: string,
  { signal }: { signal?: AbortSignal } = {}
): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(url, { method: "GET", headers: requestHeaders({ json: false }), signal });
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") throw error;
    throw new ApiError({ type: "NetworkError", message: String(error) }, 0);
  }
  if (!response.ok) throw await failure(response, url);
  return response.blob();
}

function attachmentsPath(doctype: string, name: string, fileName?: string): string {
  const base = `/document/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}/attachments`;
  return fileName === undefined ? base : `${base}/${encodeURIComponent(fileName)}`;
}

async function failure(response: Response, url: string): Promise<ApiError> {
  const text = await response.text().catch(() => "");
  const source = `GET ${url}`;
  try {
    readEnvelope(text ? JSON.parse(text) : null, response.status, { source });
  } catch (error) {
    if (error instanceof ApiError) return error;
  }
  return new ApiError(
    { type: "HTTPError", message: `${source} failed with status ${response.status}` },
    response.status
  );
}

// Every part goes to the same route and only the last one answers with `data`.
async function uploadTo<T>(
  path: string,
  file: File,
  fields: UploadFields,
  { onProgress, signal, chunkSize }: UploadOptions
): Promise<Envelope<T>> {
  const size = chunkSize && chunkSize > 0 ? chunkSize : DEFAULT_CHUNK_SIZE;
  const total = Math.max(1, Math.ceil(file.size / size));
  let answer: Envelope<T> | null = null;

  for (let index = 0; index < total; index++) {
    const offset = index * size;
    answer = await sendChunk<T>(path, {
      blob: file.slice(offset, offset + size),
      fileName: file.name,
      fields: { ...fields, ...chunkFields(index, total, offset, file.size) },
      fileSize: file.size,
      offset,
      last: index === total - 1,
      onProgress,
      signal,
    });
  }
  if (!answer) throw new ApiError({ type: "InvalidResponse", message: "The upload returned nothing" }, 0);
  return answer;
}

function chunkFields(index: number, total: number, offset: number, size: number): UploadFields {
  return {
    chunk_index: index,
    total_chunk_count: total,
    chunk_byte_offset: offset,
    total_file_size: size,
  };
}

interface ChunkRequest {
  blob: Blob;
  fileName: string;
  fields: UploadFields;
  fileSize: number;
  offset: number;
  last: boolean;
  onProgress?: (loaded: number, total: number) => void;
  signal?: AbortSignal;
}

// XHR, not fetch: only XHR reports how many bytes of the request body have gone out.
function sendChunk<T>(path: string, chunk: ChunkRequest): Promise<Envelope<T> | null> {
  return new Promise((resolve, reject) => {
    const { signal, onProgress } = chunk;
    if (signal?.aborted) {
      reject(new DOMException("Upload cancelled", "AbortError"));
      return;
    }

    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    signal?.addEventListener("abort", onAbort, { once: true });
    const done = () => signal?.removeEventListener("abort", onAbort);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress?.(chunk.offset + event.loaded, chunk.fileSize);
    });
    xhr.addEventListener("error", () => {
      done();
      reject(new ApiError({ type: "NetworkError", message: "Upload failed" }, 0));
    });
    xhr.addEventListener("abort", () => {
      done();
      reject(new DOMException("Upload cancelled", "AbortError"));
    });
    xhr.onreadystatechange = () => {
      if (xhr.readyState !== XMLHttpRequest.DONE) return;
      done();
      try {
        const envelope = readChunkResponse<T>(xhr, path, chunk.last);
        resolve(chunk.last ? envelope : null);
      } catch (error) {
        reject(error);
      }
    };

    xhr.open("POST", apiUrl(path), true);
    for (const [name, value] of Object.entries(requestHeaders({ json: false }))) {
      xhr.setRequestHeader(name, value);
    }
    xhr.send(formOf(chunk));
  });
}

function formOf({ blob, fileName, fields }: ChunkRequest): FormData {
  const form = new FormData();
  form.append("file", blob, fileName);
  for (const [name, value] of Object.entries(fields)) {
    if (value === undefined || value === null) continue;
    form.append(name, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  }
  return form;
}

function readChunkResponse<T>(xhr: XMLHttpRequest, path: string, last: boolean): Envelope<T> {
  if (xhr.status === 413) {
    throw new ApiError({ type: "FileTooLarge", message: "File size exceeds the maximum allowed limit." }, 413);
  }
  let body: unknown = null;
  try {
    body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
  } catch {
    body = null;
  }
  return readEnvelope<T>(body, xhr.status || 0, { source: `POST ${path}`, nullable: !last });
}
