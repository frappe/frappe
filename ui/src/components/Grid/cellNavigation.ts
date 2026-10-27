// Keyboard entry between grid cells, read from the rows the grid renders.

export interface CellAt {
  rowIndex: number;
  columnIndex: number;
}

type Step = [rows: number, columns: number];

export type RowShortcut = "insertAbove" | "insertBelow" | "duplicate";

const FOCUSABLE = [
  'input:not([type="hidden"]):not(:disabled)',
  "textarea:not(:disabled)",
  "select:not(:disabled)",
  "button:not(:disabled)",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

/** The cell an event came from, by its row's position and the cell's column. */
export function cellAt(target: EventTarget | null): CellAt | null {
  const cell = target instanceof Element ? target.closest<HTMLElement>(".grid-cell") : null;
  const row = cell?.closest<HTMLElement>(".grid-row");
  if (!cell || !row) return null;
  return {
    rowIndex: Number(row.dataset.idx) - 1,
    columnIndex: cellsOf(row).indexOf(cell),
  };
}

/**
 * Plain arrows move between cells. Left and Right move only from the start or
 * end of the text, and a textarea, a select or an open picker keeps its keys.
 */
export function arrowStep(e: KeyboardEvent): Step | null {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return null;
  const el = e.target as HTMLElement;
  if (keepsOwnArrows(el)) return null;
  if (e.key === "ArrowUp") return [-1, 0];
  if (e.key === "ArrowDown") return [1, 0];
  if (e.key === "ArrowLeft") return caretAt(el, "start") ? [0, -1] : null;
  if (e.key === "ArrowRight") return caretAt(el, "end") ? [0, 1] : null;
  return null;
}

/** Desk v1's keys: Ctrl/Cmd+Up or Down inserts a row, Shift+Alt+Down duplicates. */
export function rowShortcut(e: KeyboardEvent): RowShortcut | null {
  if ((e.target as HTMLElement).tagName === "TEXTAREA") return null;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.shiftKey && !e.altKey) {
    if (e.key === "ArrowUp") return "insertAbove";
    if (e.key === "ArrowDown") return "insertBelow";
  }
  if (!mod && e.shiftKey && e.altKey && e.key === "ArrowDown") return "duplicate";
  return null;
}

/** Focus the next cell along `step` that has a control, stopping at the grid's edges. */
export function moveFocus(root: HTMLElement, from: CellAt, [dr, dc]: Step): boolean {
  let at = { rowIndex: from.rowIndex + dr, columnIndex: from.columnIndex + dc };
  while (cellElement(root, at)) {
    if (focusCell(root, at)) return true;
    at = { rowIndex: at.rowIndex + dr, columnIndex: at.columnIndex + dc };
  }
  return false;
}

export function focusCell(root: HTMLElement, at: CellAt): boolean {
  const control = cellElement(root, at)?.querySelector<HTMLElement>(FOCUSABLE);
  control?.focus();
  return Boolean(control);
}

function cellElement(root: HTMLElement, at: CellAt): HTMLElement | undefined {
  if (at.rowIndex < 0 || at.columnIndex < 0) return undefined;
  const row = root.querySelectorAll<HTMLElement>(".grid-row")[at.rowIndex];
  return row ? cellsOf(row)[at.columnIndex] : undefined;
}

function cellsOf(row: HTMLElement): HTMLElement[] {
  return [...row.querySelectorAll<HTMLElement>(".grid-cell")];
}

function keepsOwnArrows(el: HTMLElement): boolean {
  if (el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable) return true;
  const open = el.closest('[aria-expanded="true"], [data-state="open"]');
  return Boolean(open && el.closest(".grid-cell")?.contains(open));
}

function caretAt(el: HTMLElement, edge: "start" | "end"): boolean {
  if (!(el instanceof HTMLInputElement)) return true;
  // Inputs without a caret (checkbox, number, date) throw or answer null here.
  let start: number | null;
  let end: number | null;
  try {
    start = el.selectionStart;
    end = el.selectionEnd;
  } catch {
    return true;
  }
  if (start == null || end == null) return true;
  if (start !== end) return false;
  return edge === "start" ? start === 0 : end === el.value.length;
}
