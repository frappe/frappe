/**
 * Headless upload orchestrator — the source-agnostic engine behind every
 * consumer (the dialog, `AttachField`, `AttachmentsList`). It owns:
 *
 *  - the queue of `UploadItem`s (reactive),
 *  - client-side validation against `Restrictions` (size / type / count) plus
 *    name+size duplicate detection, with friendly messages in `errors`,
 *  - the commit pipeline: per item, server `optimize` args (crop is applied
 *    upstream by replacing the item's `File`); link items commit directly with
 *    no POST,
 *  - per-item + aggregate progress, and cancel / retry via `AbortController`.
 *
 * The transport is injected (defaults to the Frappe one), so the engine carries
 * no backend knowledge and is unit-testable with a fake transport.
 */
import { computed, reactive, ref, type ComputedRef, type Ref } from "vue";
import type {
  Restrictions,
  UploadArgs,
  UploadItem,
  UploadResult,
  UploadTransport,
} from "./types";

// The Frappe default transport pulls in `frappe-ui`; import it lazily on first
// use so consumers that inject their own transport (and the unit tests, which
// always do) never drag `frappe-ui` into this module's graph. It also keeps the
// chunked-upload code out of the bundle until an upload actually runs.
const lazyDefaultTransport: UploadTransport = async (file, args, ctx) => {
  const { defaultTransport } = await import("./useFileUpload");
  return defaultTransport(file, args, ctx);
};

export interface UseUploaderOptions {
  /** Backend seam; defaults to Frappe's `/api/method/upload_file`. */
  transport?: UploadTransport;
  restrictions?: Restrictions;
  /** Allow more than one queued file. Single-file fields pass `false`. */
  multiple?: boolean;
  /** Restrict to images (Attach Image); also enables crop upstream. */
  imageOnly?: boolean;
  /** Initial global private default for newly added items. */
  isPrivate?: boolean;
  /** Initial global optimize default. */
  optimize?: boolean;
  folder?: string;
  maxWidth?: number;
  maxHeight?: number;
}

export interface Uploader {
  items: UploadItem[];
  errors: Ref<string[]>;
  isPrivateAll: Ref<boolean>;
  optimizeAll: Ref<boolean>;
  isUploading: ComputedRef<boolean>;
  /** Aggregate upload progress, 0..1 averaged across all queued items. */
  progress: ComputedRef<number>;
  canAddMore: ComputedRef<boolean>;
  add(files: File[] | FileList, source?: UploadItem["source"]): UploadItem[];
  addLink(url: string): UploadItem | null;
  remove(id: string): void;
  clear(): void;
  reorder(fromIndex: number, toIndex: number): void;
  replaceFile(id: string, file: File): void;
  setPrivate(id: string, value: boolean): void;
  setAllPrivate(value: boolean): void;
  /** Toggle per-item image optimization (no-op meaning for non-images). */
  setOptimize(id: string, value: boolean): void;
  cancel(id: string): void;
  cancelAll(): void;
  retry(id: string): void;
  /**
   * Upload not-yet-committed items. Returns only the results committed by THIS
   * call (the delta) — rows already `done` from a prior pass are skipped, so a
   * re-commit after a partial failure never re-emits earlier successes.
   *
   * Pass `ids` to scope the pass to specific rows (per-item retry); omit it to
   * commit every pending row. Ids not in the queue are ignored.
   */
  commit(ids?: string[]): Promise<UploadResult[]>;
}

export function useUploader(options: UseUploaderOptions = {}): Uploader {
  const transport = options.transport ?? lazyDefaultTransport;
  const restrictions = options.restrictions ?? {};
  const multiple = options.multiple ?? false;

  const items = reactive<UploadItem[]>([]);
  const errors = ref<string[]>([]);
  const isPrivateAll = ref(options.isPrivate ?? true);
  const optimizeAll = ref(options.optimize ?? false);

  // Per-item abort controllers, kept out of the reactive item so aborting
  // doesn't churn the queue. Cleared when an item leaves the queue.
  const controllers = new Map<string, AbortController>();

  const isUploading = computed(() =>
    items.some((item) => item.status === "uploading")
  );

  const progress = computed(() => {
    const list = items;
    if (!list.length) return 0;
    const total = list.reduce((sum, item) => {
      if (item.status === "done") return sum + 1;
      return sum + item.progress;
    }, 0);
    return total / list.length;
  });

  // Single source of truth for the count gate; the computed delegates to it so
  // imperative callers (add/addLink) and reactive consumers stay in sync.
  function canAddMoreInternal(): boolean {
    if (!multiple) return items.length === 0;
    const max = restrictions.max_number_of_files;
    return max == null || items.length < max;
  }

  const canAddMore = computed(() => canAddMoreInternal());

  function add(
    files: File[] | FileList,
    source: UploadItem["source"] = "device"
  ): UploadItem[] {
    errors.value = [];
    const incoming = Array.from(files);
    const added: UploadItem[] = [];

    for (const file of incoming) {
      if (!canAddMoreInternal()) {
        errors.value.push(maxFilesMessage());
        break;
      }
      const problem = validate(file);
      if (problem) {
        errors.value.push(problem);
        continue;
      }
      if (isDuplicate(file)) {
        errors.value.push(`"${file.name}" is already in the list.`);
        continue;
      }
      const item: UploadItem = reactive({
        id: uid(),
        source,
        file,
        name: file.name,
        size: file.size,
        isPrivate: isPrivateAll.value,
        // Only images can be optimized; seed non-images off so the flag never
        // rides along on, say, a PDF upload.
        optimize: file.type.startsWith("image/") ? optimizeAll.value : false,
        status: "idle",
        progress: 0,
      });
      items.push(item);
      added.push(item);
    }
    return added;
  }

  function addLink(url: string): UploadItem | null {
    errors.value = [];
    const trimmed = url.trim();
    if (!trimmed) return null;
    if (!isAllowedUrl(trimmed)) {
      errors.value.push("Only http(s) links are allowed.");
      return null;
    }
    if (items.some((item) => item.source === "link" && item.link === trimmed)) {
      errors.value.push(`"${trimmed}" is already in the list.`);
      return null;
    }
    if (!canAddMoreInternal()) {
      errors.value.push(maxFilesMessage());
      return null;
    }
    const item: UploadItem = reactive({
      id: uid(),
      source: "link",
      link: trimmed,
      name: basename(trimmed),
      isPrivate: isPrivateAll.value,
      status: "idle",
      progress: 0,
    });
    items.push(item);
    return item;
  }

  function remove(id: string): void {
    cancel(id);
    const index = items.findIndex((item) => item.id === id);
    if (index !== -1) items.splice(index, 1);
    controllers.delete(id);
  }

  function clear(): void {
    cancelAll();
    items.splice(0, items.length);
    controllers.clear();
    errors.value = [];
  }

  function reorder(fromIndex: number, toIndex: number): void {
    if (
      fromIndex < 0 ||
      toIndex < 0 ||
      fromIndex >= items.length ||
      toIndex >= items.length
    ) {
      return;
    }
    const [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);
  }

  function replaceFile(id: string, file: File): void {
    const item = items.find((entry) => entry.id === id);
    if (!item) return;
    item.file = file;
    item.name = file.name;
    item.size = file.size;
    item.status = "idle";
    item.progress = 0;
    item.error = undefined;
  }

  function setPrivate(id: string, value: boolean): void {
    const item = items.find((entry) => entry.id === id);
    if (item) item.isPrivate = value;
  }

  function setAllPrivate(value: boolean): void {
    isPrivateAll.value = value;
    for (const item of items) item.isPrivate = value;
  }

  function setOptimize(id: string, value: boolean): void {
    const item = items.find((entry) => entry.id === id);
    if (item) item.optimize = value;
  }

  function cancel(id: string): void {
    controllers.get(id)?.abort();
  }

  function cancelAll(): void {
    for (const controller of controllers.values()) controller.abort();
  }

  function retry(id: string): void {
    const item = items.find((entry) => entry.id === id);
    if (item && item.status === "error") {
      item.status = "idle";
      item.progress = 0;
      item.error = undefined;
    }
  }

  async function commit(ids?: string[]): Promise<UploadResult[]> {
    // Re-entrancy guard: if a full pass is already in flight, don't start a
    // second concurrent one — bail out rather than double-uploading items.
    // Scoped commits (per-item retry) are exempt: while the tray's sequential
    // loop uploads item N+1, retrying the already-failed item N must go through,
    // or N gets stuck idle with no retry button until the tray is closed.
    if (!ids && isUploading.value) return [];

    // Optional scope for per-item retry: when given, only these rows are
    // committed and the rest are left untouched (e.g. other failed rows stay
    // failed). Omitted → commit every pending row.
    const scope = ids ? new Set(ids) : null;

    const results: UploadResult[] = [];
    // Sequential, mirroring desk — keeps progress legible and avoids
    // hammering the server with N concurrent large uploads.
    // Snapshot the queue so a mid-commit remove/reorder can't shift the
    // iterator and skip or double-process a not-yet-handled item. Each `item`
    // is still the same reactive object, so status/progress stay reactive.
    for (const item of [...items]) {
      if (scope && !scope.has(item.id)) continue;
      // Skip items already committed by an earlier pass. We return only the
      // delta committed in THIS call — a re-commit (e.g. retrying a failed row
      // after a partial success) must not re-emit the rows that already
      // succeeded, or consumers like AttachmentsList would append them twice.
      if (item.status === "done") continue;

      // A web link is stored directly — no upload.
      if (item.source === "link" && item.link) {
        item.status = "done";
        item.progress = 1;
        item.fileUrl = item.link;
        results.push(toResult(item, item.link));
        continue;
      }

      if (!item.file) continue;

      const controller = new AbortController();
      controllers.set(item.id, controller);
      item.status = "uploading";
      item.progress = 0;
      item.error = undefined;

      const args: UploadArgs = {
        isPrivate: item.isPrivate,
        folder: options.folder,
        // Per-item now; fall back to the global default for consumers that only
        // set `optimizeAll` and never touch individual items.
        optimize: item.optimize ?? optimizeAll.value,
        maxWidth: options.maxWidth,
        maxHeight: options.maxHeight,
      };

      try {
        const { file_url } = await transport(item.file, args, {
          signal: controller.signal,
          onProgress: (loaded, total) => {
            item.progress = total > 0 ? loaded / total : 0;
          },
        });
        item.status = "done";
        item.progress = 1;
        item.fileUrl = file_url;
        results.push(toResult(item, file_url));
      } catch (error: any) {
        item.status = "error";
        item.error =
          error?.name === "AbortError"
            ? "Cancelled"
            : error?.message || "Upload failed";
      } finally {
        controllers.delete(item.id);
      }
    }
    return results;
  }

  // ── internals ────────────────────────────────────────────────────────────

  function toResult(item: UploadItem, fileUrl: string): UploadResult {
    return {
      file_url: fileUrl,
      file_name: item.name,
      is_private: item.isPrivate,
    };
  }

  // Accept only absolute http/https URLs or site-relative paths ("/files/x").
  // Parsing against a dummy http base means a relative path resolves to http(s)
  // and passes, while `javascript:`/`data:`/`vbscript:` keep their own protocol
  // and are rejected — closing the clickable-XSS vector before we store the link.
  function isAllowedUrl(url: string): boolean {
    try {
      const { protocol } = new URL(url, "http://x");
      return protocol === "http:" || protocol === "https:";
    } catch {
      return false;
    }
  }

  function isDuplicate(file: File): boolean {
    return items.some(
      (item) => item.name === file.name && item.size === file.size
    );
  }

  /** Returns a friendly error string when the file is rejected, else null. */
  function validate(file: File): string | null {
    const allowed = effectiveAllowedTypes();
    if (
      allowed.length &&
      !matchesType(file, allowed) &&
      !typelessPasses(file, allowed)
    ) {
      return `"${file.name}" was skipped — file type not allowed.`;
    }
    const max = restrictions.max_file_size;
    if (max != null && file.size != null && file.size > max) {
      return `"${file.name}" was skipped — exceeds ${formatBytes(max)}.`;
    }
    return null;
  }

  // OS-reported-typeless files (empty `file.type`) can't match a MIME rule, so a
  // MIME-only restriction would wrongly skip them. Treat them as a best-effort
  // pass when the only rules are MIME rules (the server re-validates the real
  // type). Extension rules are still authoritative: if any are present they must
  // match, so this never loosens extension-only restrictions.
  function typelessPasses(file: File, allowed: string[]): boolean {
    if (file.type) return false;
    const rules = allowed.map((t) => t.trim()).filter(Boolean);
    const hasExtensionRule = rules.some(
      (t) => t[0] === "." && !t.includes("/")
    );
    const hasMimeRule = rules.some((t) => t.includes("/"));
    return hasMimeRule && !hasExtensionRule;
  }

  function effectiveAllowedTypes(): string[] {
    if (restrictions.allowed_file_types?.length) {
      return restrictions.allowed_file_types;
    }
    return options.imageOnly ? ["image/*"] : [];
  }

  function maxFilesMessage(): string {
    const max = multiple ? restrictions.max_number_of_files : 1;
    return `Only ${max} file${max === 1 ? "" : "s"} allowed.`;
  }

  return {
    items,
    errors,
    isPrivateAll,
    optimizeAll,
    isUploading,
    progress,
    canAddMore,
    add,
    addLink,
    remove,
    clear,
    reorder,
    replaceFile,
    setPrivate,
    setAllPrivate,
    setOptimize,
    cancel,
    cancelAll,
    retry,
    commit,
  };
}

/** Matches a file against an extension (".png") or MIME glob ("image/*"). */
export function matchesType(file: File, types: string[]): boolean {
  return types.some((type) => {
    const t = type.trim();
    if (!t) return false;
    if (t.includes("/")) {
      if (!file.type) return false;
      if (t.endsWith("/*")) return file.type.startsWith(t.slice(0, -1));
      return file.type === t;
    }
    if (t[0] === ".") return file.name.toLowerCase().endsWith(t.toLowerCase());
    return false;
  });
}

/** Human-readable byte size for validation messages. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

function basename(url: string): string {
  try {
    const path = new URL(url).pathname;
    const last = path.split("/").filter(Boolean).pop();
    return last ? decodeURIComponent(last) : url;
  } catch {
    return url.split("/").filter(Boolean).pop() || url;
  }
}

let idSeq = 0;
/** Collision-free queue-item id without Math.random(). */
function uid(): string {
  return `upload-${++idSeq}`;
}
