/**
 * Default upload transport for the file primitive.
 *
 * Small files ride frappe-ui's `useFileUpload` (XHR + progress + `AbortSignal`).
 * Files above the chunk threshold (~25 MB) use a ported version of desk's
 * sequential chunk loop (`FileUploader.vue`) — frappe-ui's uploader does not
 * chunk, and a single XHR for a multi-hundred-MB file is fragile. Both paths
 * resolve to `{ file_url }` so the queue is unaware which ran.
 *
 * Consumers that talk to a non-Frappe backend inject their own `UploadTransport`
 * into `useUploader` / the dialog; this module is only the default.
 */
import { useFileUpload as useFrappeFileUpload } from "frappe-ui";
import type { UploadArgs, UploadTransport } from "./types";

/** Default Frappe folder for detached uploads (FormLayout fields lack a docname). */
const DEFAULT_FOLDER = "Home/Attachments";

/**
 * Chunk threshold (and slice size): files above it use the chunked loop.
 * Mirrors desk's 25 MB default. Read per upload, not once at import — `frappe.boot`
 * may not be populated when this module first loads, and a stale fallback would
 * pin the whole session to 25 MB even after boot arrives.
 */
function chunkSize(): number {
  const boot = (globalThis as any).frappe?.boot;
  return boot?.file_chunk_size || 25 * 1024 * 1024;
}

/** CSRF token if the host page exposes one (desk / a Frappe SPA). */
function csrfToken(): string | null {
  const token = (globalThis as any).csrf_token;
  return token && token !== "{{ csrf_token }}" ? token : null;
}

/**
 * Build the default transport. Each call to the returned transport creates a
 * fresh `useFileUpload` instance, so concurrent uploads never share progress
 * state.
 */
export function createFrappeTransport(): UploadTransport {
  return (file, args, ctx) => {
    const chunk = chunkSize();
    if (file.size > chunk) {
      return uploadChunked(file, args, ctx, chunk);
    }
    return uploadWhole(file, args, ctx);
  };
}

/** The shared default instance used when no transport is injected. */
export const defaultTransport: UploadTransport = createFrappeTransport();

async function uploadWhole(
  file: File,
  args: UploadArgs,
  ctx: {
    signal: AbortSignal;
    onProgress: (loaded: number, total: number) => void;
  }
): Promise<{ file_url: string }> {
  const { upload } = useFrappeFileUpload();
  const result = await upload(file, {
    private: args.isPrivate,
    folder: args.folder || DEFAULT_FOLDER,
    optimize: args.optimize,
    max_width: args.maxWidth,
    max_height: args.maxHeight,
    signal: ctx.signal,
    onProgress: ({ loaded, total }) => ctx.onProgress(loaded, total),
  });
  return { file_url: result.file_url };
}

/**
 * Ported desk chunk loop: slice the file into `chunkSize` blobs and POST them
 * sequentially with `chunk_index` / `total_chunk_count` / `chunk_byte_offset`.
 * Only the final chunk's response carries the File doc. Progress is reported as
 * `chunk_byte_offset + chunk.loaded` against the whole file size; the shared
 * `AbortSignal` aborts the in-flight chunk and stops the loop.
 */
async function uploadChunked(
  file: File,
  args: UploadArgs,
  ctx: {
    signal: AbortSignal;
    onProgress: (loaded: number, total: number) => void;
  },
  chunkSize: number
): Promise<{ file_url: string }> {
  const totalChunks = Math.ceil(file.size / chunkSize);

  const sendChunk = (
    blob: Blob,
    chunkIndex: number,
    offset: number
  ): Promise<{ file_url: string } | null> =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      const onAbort = () => xhr.abort();
      if (ctx.signal.aborted) {
        reject(new DOMException("Upload cancelled", "AbortError"));
        return;
      }
      ctx.signal.addEventListener("abort", onAbort, { once: true });

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) ctx.onProgress(offset + e.loaded, file.size);
      });

      xhr.addEventListener("error", () => {
        ctx.signal.removeEventListener("abort", onAbort);
        reject(new Error("Upload failed"));
      });

      xhr.addEventListener("abort", () => {
        ctx.signal.removeEventListener("abort", onAbort);
        reject(new DOMException("Upload cancelled", "AbortError"));
      });

      xhr.onreadystatechange = () => {
        if (xhr.readyState !== XMLHttpRequest.DONE) return;
        ctx.signal.removeEventListener("abort", onAbort);
        if (xhr.status === 200) {
          // Only the last chunk returns the assembled File doc.
          if (chunkIndex === totalChunks - 1) {
            let message: any = null;
            try {
              message = JSON.parse(xhr.responseText)?.message;
            } catch {
              /* non-JSON 200 — treated as a missing url below */
            }
            resolve(message?.file_url ? { file_url: message.file_url } : null);
          } else {
            resolve(null);
          }
        } else {
          reject(new Error(uploadErrorMessage(xhr)));
        }
      };

      xhr.open("POST", "/api/method/upload_file", true);
      xhr.setRequestHeader("Accept", "application/json");
      const token = csrfToken();
      if (token) xhr.setRequestHeader("X-Frappe-CSRF-Token", token);

      const form = new FormData();
      form.append("file", blob, file.name);
      form.append("is_private", args.isPrivate ? "1" : "0");
      form.append("folder", args.folder || DEFAULT_FOLDER);
      form.append("total_file_size", String(file.size));
      form.append("chunk_index", String(chunkIndex));
      form.append("total_chunk_count", String(totalChunks));
      form.append("chunk_byte_offset", String(offset));
      if (args.optimize) {
        form.append("optimize", "1");
        if (args.maxWidth) form.append("max_width", String(args.maxWidth));
        if (args.maxHeight) form.append("max_height", String(args.maxHeight));
      }
      xhr.send(form);
    });

  let result: { file_url: string } | null = null;
  let offset = 0;
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const blob = file.slice(offset, offset + chunkSize);
    result = await sendChunk(blob, chunkIndex, offset);
    offset += chunkSize;
  }
  if (!result?.file_url) {
    throw new Error("Upload completed but no file URL was returned");
  }
  return result;
}

/** Best-effort error text from a failed chunk response. */
function uploadErrorMessage(xhr: XMLHttpRequest): string {
  if (xhr.status === 413) return "File size exceeds the maximum allowed limit.";
  try {
    const error = JSON.parse(xhr.responseText);
    if (error?._server_messages) {
      const messages = JSON.parse(error._server_messages)
        .map((m: string) => {
          try {
            return JSON.parse(m).message;
          } catch {
            return m;
          }
        })
        .filter(Boolean);
      if (messages.length) return messages.join("\n");
    }
    if (error?._error_message) return error._error_message;
  } catch {
    /* non-JSON error body */
  }
  return `Upload failed (${xhr.status || "network error"})`;
}
