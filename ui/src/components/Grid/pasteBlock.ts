// A block copied from a spreadsheet: cells split by tabs, rows by newlines.

export interface PasteWrite {
  rowIndex: number;
  columnIndex: number;
  text: string;
}

export interface PastePlan {
  /** Rows to append before the writes, for a block taller than the rows left. */
  addRows: number;
  writes: PasteWrite[];
}

export interface PasteTarget {
  rowIndex: number;
  columnIndex: number;
  rowCount: number;
  columns: { fieldname: string; label?: string }[];
  canAddRows: boolean;
}

/** A pasted value is a block when it spans more than one cell. */
export function isBlock(block: string[][]): boolean {
  return block.length > 1 || (block[0]?.length ?? 0) > 1;
}

/** Only a text input takes a block, as in desk v1; a textarea keeps its own paste. */
export function acceptsPaste(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement && !["checkbox", "radio", "file"].includes(target.type)
  );
}

/**
 * Where each pasted cell lands: right and below from the target cell. A first
 * line that names a column (label or fieldname) is a header and maps the
 * columns instead, as in desk v1. Without `canAddRows` the lines past the last
 * row are dropped.
 */
export function planPaste(block: string[][], target: PasteTarget): PastePlan {
  const header = headerColumns(block[0], target.columns);
  const lines = header ? block.slice(1) : block;
  const room = target.canAddRows ? lines.length : target.rowCount - target.rowIndex;
  const kept = lines.slice(0, Math.max(0, room));
  const writes: PasteWrite[] = [];
  kept.forEach((cells, offset) => {
    if (cells.every((text) => !text)) return;
    cells.forEach((text, n) => {
      const columnIndex = header ? header[n] : target.columnIndex + n;
      if (columnIndex >= 0 && columnIndex < target.columns.length) {
        writes.push({ rowIndex: target.rowIndex + offset, columnIndex, text });
      }
    });
  });
  const addRows = Math.max(0, target.rowIndex + kept.length - target.rowCount);
  return { addRows, writes };
}

/** Cells of a tab-separated block. A quoted cell may hold tabs, newlines and `""`. */
export function parseBlock(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"' && cell === "") quoted = true;
    else if (ch === "\t") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      rows.push([...row, cell]);
      row = [];
      cell = "";
    } else cell += ch;
  }
  rows.push([...row, cell]);
  // Excel ends every copy with a newline.
  while (rows.length && rows[rows.length - 1].every((c) => !c)) rows.pop();
  return rows;
}

function headerColumns(
  first: string[] | undefined,
  columns: PasteTarget["columns"]
): number[] | null {
  if (!first?.[0] || columnIndexOf(first[0], columns) < 0) return null;
  return first.map((name) => columnIndexOf(name, columns));
}

function columnIndexOf(name: string, columns: PasteTarget["columns"]): number {
  const wanted = name.trim().toLowerCase();
  return columns.findIndex(
    (c) => c.fieldname.toLowerCase() === wanted || c.label?.toLowerCase() === wanted
  );
}
