/** Default upload transport: the chunk loop against `/api/v2/method/upload_file`; a small file is one chunk. */
import { apiUrl, isApiError, readEnvelope, requestHeaders, UPLOAD_PATH } from "../../api";
import type { UploadArgs, UploadTransport } from "./types";

/** Default Frappe folder for detached uploads (FormLayout fields lack a docname). */
const DEFAULT_FOLDER = "Home/Attachments";

// Read per upload, not at import: `frappe.boot` may not be populated when this module loads.
function chunkSize(): number {
  const boot = (globalThis as any).frappe?.boot;
  return boot?.file_chunk_size || 25 * 1024 * 1024;
}

export function createFrappeTransport(): UploadTransport {
  return (file, args, ctx) => uploadChunked(file, args, ctx, chunkSize());
}

/** The shared default instance used when no transport is injected. */
export const defaultTransport: UploadTransport = createFrappeTransport();

// Only the final chunk's response carries the File doc; the shared signal aborts the loop.
async function uploadChunked(
  file: File,
  args: UploadArgs,
  ctx: {
    signal: AbortSignal;
    onProgress: (loaded: number, total: number) => void;
  },
  chunkSize: number
): Promise<{ file_url: string }> {
  const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));

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
        if (xhr.status !== 200) {
          reject(new Error(uploadErrorMessage(xhr)));
        } else if (chunkIndex === totalChunks - 1) {
          resolve(readFileUrl(xhr.responseText));
        } else {
          resolve(null);
        }
      };

      xhr.open("POST", apiUrl(UPLOAD_PATH), true);
      for (const [name, value] of Object.entries(requestHeaders({ json: false }))) {
        xhr.setRequestHeader(name, value);
      }

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

function readFileUrl(responseText: string): { file_url: string } | null {
  try {
    const { data } = readEnvelope<{ file_url?: string } | null>(JSON.parse(responseText), 200);
    return data?.file_url ? { file_url: data.file_url } : null;
  } catch {
    return null;
  }
}

/** Best-effort error text from a failed chunk response. */
function uploadErrorMessage(xhr: XMLHttpRequest): string {
  if (xhr.status === 413) return "File size exceeds the maximum allowed limit.";
  try {
    readEnvelope(JSON.parse(xhr.responseText), xhr.status);
  } catch (error) {
    if (isApiError(error)) return error.message;
  }
  return `Upload failed (${xhr.status || "network error"})`;
}
