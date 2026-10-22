import { onScopeDispose, reactive, ref } from "vue";
import type { ListColumn } from "./types";

const MIN_COLUMN_WIDTH = 60;
const DRAG_THRESHOLD = 3;

interface Drag {
  fieldname: string;
  startX: number;
  startWidth: number;
}

/** Drag-resize on a header cell: a draft width while dragging, the final width on release.
 *  The draft clears as `onResize` fires, so the host writes the width into its columns synchronously. */
export function useColumnResize(handlers: {
  onResize: (fieldname: string, width: string) => void;
  onReset: (fieldname: string) => void;
}) {
  const drafts = reactive<Record<string, string>>({});
  const resizingFieldname = ref<string | null>(null);
  let drag: Drag | null = null;

  function startResize(column: ListColumn, event: PointerEvent) {
    const cell = (event.currentTarget as HTMLElement).parentElement;
    if (!cell) return;
    drag = {
      fieldname: column.fieldname,
      startX: event.clientX,
      startWidth: cell.getBoundingClientRect().width,
    };
    resizingFieldname.value = column.fieldname;
    window.addEventListener("pointermove", onDrag);
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", cancelDrag);
  }

  function onDrag(event: PointerEvent) {
    if (!drag) return;
    if (Math.abs(event.clientX - drag.startX) < DRAG_THRESHOLD) return;
    const width = Math.max(
      MIN_COLUMN_WIDTH,
      drag.startWidth + (event.clientX - drag.startX)
    );
    drafts[drag.fieldname] = `${Math.round(width)}px`;
  }

  function endDrag() {
    stopListening();
    resizingFieldname.value = null;
    if (!drag) return;
    const { fieldname } = drag;
    const width = drafts[fieldname];
    delete drafts[fieldname];
    drag = null;
    if (width) handlers.onResize(fieldname, width);
  }

  // A cancelled pointer (a touch the browser took for a scroll) discards the draft.
  function cancelDrag() {
    stopListening();
    resizingFieldname.value = null;
    if (drag) delete drafts[drag.fieldname];
    drag = null;
  }

  function resetColumn(column: ListColumn) {
    delete drafts[column.fieldname];
    handlers.onReset(column.fieldname);
  }

  function stopListening() {
    window.removeEventListener("pointermove", onDrag);
    window.removeEventListener("pointerup", endDrag);
    window.removeEventListener("pointercancel", cancelDrag);
  }

  onScopeDispose(stopListening);

  return { drafts, resizingFieldname, startResize, resetColumn };
}
