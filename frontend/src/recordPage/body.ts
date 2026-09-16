// The body surface: the row under the header as one list of columns, the two built-ins
// and the columns a script puts around them; and the maths the host draws a column by.
import { Surface } from "./surface";
import { BODY_ITEM_KEYS } from "./types";
import type { BodyItem, Position } from "./types";

/** A column with `width` and no bounds of its own is bounded by these. */
export const SCRIPT_COLUMN_DEFAULTS = { width: 320, minWidth: 240, maxWidth: 640 };
/** A flex column never drops below this; the host drops fixed columns instead. */
export const FLEX_MIN_WIDTH = 320;
export const STRIP_WIDTH = 48;
export const SNAP_DISTANCE = 7;
/** A drag this far under `minWidth` shuts a collapsible column instead of resizing it. */
export const COLLAPSE_SLACK = 60;
export const REOPEN_DISTANCE = 40;
const SEPARATOR_WIDTH = 1;

/** The columns the host draws, in row order; a script column is addressed relative to them. */
export const BODY_BUILTINS: readonly BodyItem[] = [
  { name: "form", gutter: false },
  { name: "panel", gutter: false, width: 380, minWidth: 320, maxWidth: 640, collapsible: true },
];

export class BodySurface extends Surface<BodyItem> {
  constructor() {
    super({ surface: "body", keys: BODY_ITEM_KEYS });
    this.provideBuiltins(() => BODY_BUILTINS.map((item) => ({ ...item })));
  }

  add(item: BodyItem | BodyItem[], position?: Position) {
    const columns = (Array.isArray(item) ? item : [item]).filter((one) => {
      if (!isBuiltin(one.name)) return true;
      warn(`page.body.add('${one.name}') — '${one.name}' is a built-in column: a column needs a name of its own; nothing was added.`);
      return false;
    });
    if (columns.length) super.add(columns, position);
  }

  hide(name: string) {
    if (name === "form") warn("page.body.hide('form') — the Details form is hidden; the panel still reads page.fields.");
    super.hide(name);
  }
}

export interface ColumnBounds {
  width: number;
  minWidth: number;
  maxWidth: number;
}

/** The fixed column's default width and its drag range; `null` for a column that flexes. */
export function columnBounds(item: BodyItem): ColumnBounds | null {
  if (typeof item.width !== "number") return null;
  const minWidth = item.minWidth ?? SCRIPT_COLUMN_DEFAULTS.minWidth;
  const maxWidth = Math.max(item.maxWidth ?? SCRIPT_COLUMN_DEFAULTS.maxWidth, minWidth);
  return { width: clamp(item.width, minWidth, maxWidth), minWidth, maxWidth };
}

/** What the reader left behind for one column, by name. */
export interface Remembered {
  width?: number;
  collapsed?: boolean;
}

export type EdgeSide = "left" | "right";

/** One column as the host draws it. */
export interface BodyColumn {
  item: BodyItem;
  /** The drag range; `null` on a flex column. */
  bounds: ColumnBounds | null;
  /** The open width, the reader's memory clamped to the bounds; `0` on a flex column. */
  width: number;
  collapsible: boolean;
  /** Shut by the reader, or by the host because the row was too narrow. */
  collapsed: boolean;
  /** Too narrow a row: not drawn, or drawn as a strip when collapsible. */
  dropped: boolean;
  /** Where the drag edge sits: facing the nearest flex column, none without one. */
  edge: EdgeSide | null;
}

/** Lays the visible items out in `available` px: widths, what shuts, what drops, and the edges. */
export function projectBody(
  items: BodyItem[],
  remembered: (name: string) => Remembered | undefined,
  available: number,
): BodyColumn[] {
  const columns = items.map((item) => layColumn(item, remembered(item.name)));
  if (available > 0) fit(columns, available);
  placeEdges(columns);
  return columns;
}

/** Whether the column takes room in the row at all. */
export function isDrawn(column: BodyColumn) {
  return !column.dropped || column.collapsible;
}

/** The room a drawn column takes: its strip, its width, or the flex minimum. */
export function drawnWidth(column: BodyColumn) {
  if (!column.bounds) return FLEX_MIN_WIDTH;
  return column.collapsed ? STRIP_WIDTH : column.width;
}

function layColumn(item: BodyItem, memory: Remembered | undefined): BodyColumn {
  const bounds = columnBounds(item);
  const collapsible = bounds !== null && item.collapsible === true;
  const kept = typeof memory?.width === "number" ? memory.width : NaN;
  const width = bounds ? clamp(Number.isFinite(kept) ? kept : bounds.width, bounds.minWidth, bounds.maxWidth) : 0;
  return {
    item,
    bounds,
    width,
    collapsible,
    collapsed: collapsible && memory?.collapsed === true,
    dropped: false,
    edge: null,
  };
}

function fit(columns: BodyColumn[], available: number) {
  if (!columns.some((column) => !column.bounds)) return;
  for (const at of dropOrder(columns)) {
    if (needed(columns) <= available) return;
    columns[at].dropped = true;
    if (columns[at].collapsible) columns[at].collapsed = true;
  }
}

function needed(columns: BodyColumn[]) {
  const drawn = columns.filter(isDrawn);
  const separators = Math.max(drawn.length - 1, 0) * SEPARATOR_WIDTH;
  return drawn.reduce((sum, column) => sum + drawnWidth(column), separators);
}

// Outside in: right of the panel, left of the form, the panel, then between the two.
function dropOrder(columns: BodyColumn[]) {
  const fixed = columns.map((column, at) => (column.bounds ? at : -1)).filter((at) => at >= 0);
  const anchors = ["form", "panel"]
    .map((name) => columns.findIndex((column) => column.item.name === name))
    .filter((at) => at >= 0);
  const low = anchors.length ? Math.min(...anchors) : columns.length;
  const high = anchors.length ? Math.max(...anchors) : -1;
  const panel = columns.findIndex((column) => column.item.name === "panel");
  return [
    ...fixed.filter((at) => at > high).reverse(),
    ...fixed.filter((at) => at < low),
    ...fixed.filter((at) => at === panel),
    ...fixed.filter((at) => at > low && at < high && at !== panel).reverse(),
  ];
}

function placeEdges(columns: BodyColumn[]) {
  const drawn = columns.filter(isDrawn);
  const flex = drawn.map((column, at) => (column.bounds ? -1 : at)).filter((at) => at >= 0);
  drawn.forEach((column, at) => {
    if (!column.bounds || column.dropped || !flex.length) return;
    const nearest = flex.reduce((best, one) =>
      Math.abs(one - at) < Math.abs(best - at) ? one : best,
    );
    column.edge = nearest < at ? "left" : "right";
  });
}

/** What a drag on a column's edge amounts to: a new width, a toggle, or neither yet. */
export function dragOutcome(
  open: boolean,
  startWidth: number,
  distance: number,
  bounds: ColumnBounds,
  collapsible: boolean,
): { width?: number; toggle?: boolean } {
  if (!open) return distance >= REOPEN_DISTANCE ? { toggle: true } : {};
  const width = startWidth + distance;
  // A drag that ends in a collapse commits no resize, so the strip reopens at the width
  // it had before the drag squashed it against the minimum.
  if (collapsible && width < bounds.minWidth - COLLAPSE_SLACK)
    return { width: clamp(startWidth, bounds.minWidth, bounds.maxWidth), toggle: true };
  return { width: snapToDefault(clamp(width, bounds.minWidth, bounds.maxWidth), bounds.width) };
}

/** A drag that passes close to the column's default width settles on it. */
export function snapToDefault(width: number, defaultWidth: number) {
  return Math.abs(width - defaultWidth) <= SNAP_DISTANCE ? defaultWidth : width;
}

function clamp(width: number, min: number, max: number) {
  if (!Number.isFinite(width)) return min;
  return Math.min(Math.max(width, min), max);
}

function isBuiltin(name: string) {
  return BODY_BUILTINS.some((item) => item.name === name);
}

function warn(message: string) {
  if (import.meta.env.DEV) console.warn(`[record-page] ${message}`);
}
