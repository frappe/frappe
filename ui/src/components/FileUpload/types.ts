/**
 * Data contracts for the file-upload primitive. Field components (`Attach`,
 * `Attach Image`, `Image`) and the standalone `AttachmentsList` are thin
 * consumers of this engine; the contracts here are what the headless layer
 * (`useFileUpload`, `useUploader`, `uploadTray`) and the views agree on.
 *
 * The primitive is backend-agnostic: the default `UploadTransport` talks to
 * Frappe's `/api/method/upload_file`, but any consumer can inject its own.
 */

/**
 * Per-upload server options. Mirrors the `upload_file` form fields the default
 * transport sends. Folder defaults to `Home/Attachments`; `optimize` (+ the
 * optional max dimensions) asks the server to compress/downscale an image.
 */
export interface UploadArgs {
  isPrivate?: boolean;
  /** Frappe File folder; default `"Home/Attachments"`. */
  folder?: string;
  optimize?: boolean;
  maxWidth?: number;
  maxHeight?: number;
}

/**
 * The single seam between the queue and a backend. Receives one file plus its
 * args and a context carrying an `AbortSignal` (cancel) and an `onProgress`
 * callback (bytes loaded / total). Resolves with at least the resulting
 * `file_url`. Swap this out for non-Frappe backends; the default wraps
 * frappe-ui's `useFileUpload` and ports desk's chunked loop for large files.
 */
export type UploadTransport = (
  file: File,
  args: UploadArgs,
  ctx: {
    signal: AbortSignal;
    onProgress: (loaded: number, total: number) => void;
  }
) => Promise<{ file_url: string }>;

/**
 * Upload restrictions, in desk's shape (`max_file_size` in bytes,
 * `allowed_file_types` as extensions/MIME globs). Enforced client-side by the
 * uploader before any bytes leave the browser.
 */
export interface Restrictions {
  max_file_size?: number | null;
  max_number_of_files?: number | null;
  allowed_file_types?: string[];
  crop_image_aspect_ratio?: number | null;
}

/**
 * One item in the upload queue. A `device`/`camera`/`paste` item carries a
 * `File`; a `link` item carries a URL string and is committed directly (no
 * POST). `progress` is a 0..1 fraction; `status` walks idle → uploading →
 * done/error.
 */
export interface UploadItem {
  id: string;
  source: "device" | "camera" | "link" | "paste";
  file?: File;
  link?: string;
  name: string;
  size?: number;
  isPrivate: boolean;
  /**
   * Ask the server to compress/downscale this item on upload. Meaningful only
   * for raster images — the server's optimizer ignores other types — so the
   * dialog surfaces it as a per-image action, not a queue-wide one.
   */
  optimize?: boolean;
  status: "idle" | "uploading" | "done" | "error";
  /** 0..1. */
  progress: number;
  error?: string;
  fileUrl?: string;
}

/**
 * What a committed upload yields to the consumer. `AttachField` keeps the first
 * `file_url`; `AttachmentsList` keeps the whole array.
 */
export interface UploadResult {
  file_url: string;
  file_name: string;
  is_private: boolean;
}

/**
 * Which view renders an upload's progress:
 *  - `inline`  — per-row bar + footer summary (dialog default)
 *  - `tray`    — minimized floating card that survives the dialog closing
 *  - `field`   — surface spinner on the consuming field
 *  - `toast`   — terminal state when the user left both dialog and tray
 */
export type ProgressMode = "inline" | "tray" | "field" | "toast";
