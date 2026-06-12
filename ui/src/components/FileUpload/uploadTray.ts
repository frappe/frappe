/**
 * Module-level shared store backing the floating `UploadTray`. An upload started
 * from a dialog registers its queue here, so progress survives the dialog
 * closing: the inline dialog list and the bottom-left tray are two views of the
 * same `UploadItem[]`.
 *
 * This is a tiny hand-rolled store (one process-wide reactive array of batches)
 * rather than a composable, because the `UploadTray` singleton mounted at the
 * app root and any number of dialogs must all observe the same state.
 */
import { computed, reactive } from "vue";
import type { UploadItem } from "./types";

/** One tray entry: a label plus a live reference to a uploader's queue. */
export interface TrayBatch {
  id: string;
  label: string;
  items: UploadItem[];
  /** Optional per-item cancel/retry, wired from the owning uploader. */
  cancel?: (id: string) => void;
  retry?: (id: string) => void;
}

const batches = reactive<TrayBatch[]>([]);

let traySeq = 0;

/** Register a queue with the tray; returns the batch id for later removal. */
export function pushTrayBatch(
  label: string,
  items: UploadItem[],
  handlers: { cancel?: (id: string) => void; retry?: (id: string) => void } = {}
): string {
  const id = `tray-${++traySeq}`;
  batches.push({
    id,
    label,
    items,
    cancel: handlers.cancel,
    retry: handlers.retry,
  });
  return id;
}

export function removeTrayBatch(id: string): void {
  const index = batches.findIndex((batch) => batch.id === id);
  if (index !== -1) batches.splice(index, 1);
}

/** Drop every batch whose items are all in a terminal (done) state. */
export function clearFinishedBatches(): void {
  for (let i = batches.length - 1; i >= 0; i--) {
    const batch = batches[i];
    if (
      batch.items.length &&
      batch.items.every((item) => item.status === "done")
    ) {
      batches.splice(i, 1);
    }
  }
}

/**
 * Drop every batch unconditionally — the explicit user "close" on the tray.
 * Unlike `clearFinishedBatches`, this also removes batches that settled with a
 * failure (otherwise the ✕ would be a no-op on a partly-failed batch and strand
 * the tray on screen with no way to dismiss it). Any still-uploading transfer
 * keeps running in the background; this only removes the progress view.
 */
export function clearAllBatches(): void {
  batches.splice(0, batches.length);
}

/** The reactive list of batches the tray renders. */
export function useTray() {
  const activeBatches = computed(() => batches);
  const isUploading = computed(() =>
    batches.some((batch) =>
      batch.items.some((item) => item.status === "uploading")
    )
  );
  const allDone = computed(
    () =>
      batches.length > 0 &&
      batches.every((batch) =>
        batch.items.every((item) => item.status === "done")
      )
  );
  return { batches: activeBatches, isUploading, allDone };
}
