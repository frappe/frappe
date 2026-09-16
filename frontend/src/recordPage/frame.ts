// The frame surface: the page's column as one list, the two built-in regions and
// the bands a script puts before, between and after them.
import { Surface, type ResolvedItem } from "./surface";
import { FRAME_ITEM_KEYS } from "./types";
import type { FrameItem, Position } from "./types";

/** The regions the host draws, in column order; a band is addressed relative to them. */
export const FRAME_BUILTINS: readonly FrameItem[] = [{ name: "header" }, { name: "body" }];

export class FrameSurface extends Surface<FrameItem> {
  constructor() {
    super({ surface: "frame", keys: FRAME_ITEM_KEYS });
    this.provideBuiltins(() => FRAME_BUILTINS.map((item) => ({ ...item })));
  }

  add(item: FrameItem | FrameItem[], position?: Position) {
    const bands = (Array.isArray(item) ? item : [item]).filter((one) => {
      if (!isBuiltin(one.name)) return true;
      warnBuiltin("add", one.name, "a band needs a name of its own; nothing was added");
      return false;
    });
    if (bands.length) super.add(bands, position);
  }

  move(name: string, position: Position) {
    if (isBuiltin(name)) return warnBuiltin("move", name, "a region keeps its place; nothing was moved");
    super.move(name, position);
  }

  order(names: string[]) {
    for (const name of names.filter(isBuiltin))
      warnBuiltin("order", name, "a region keeps its place; it was left out of the order");
    super.order(names.filter((name) => !isBuiltin(name)));
  }
}

/** The column as the host draws it: each region's visibility, and the visible bands around them. */
export interface FrameProjection {
  before: FrameItem[];
  header: boolean;
  between: FrameItem[];
  body: boolean;
  after: FrameItem[];
}

/** Buckets the resolved list by the two regions' places; with no list at all both regions show. */
export function projectFrame(resolved: ResolvedItem<FrameItem>[]): FrameProjection {
  const index = (name: string) => resolved.findIndex((entry) => entry.item.name === name);
  const shown = (name: string) => resolved[index(name)]?.hidden !== true;
  const header = index("header");
  const body = index("body");
  const bands = (from: number, to: number) =>
    resolved
      .filter((entry, at) => at > from && at < to && !entry.hidden && !isBuiltin(entry.item.name))
      .map((entry) => entry.item);
  return {
    before: bands(-1, header),
    header: shown("header"),
    between: bands(header, body),
    body: shown("body"),
    after: bands(body, resolved.length),
  };
}

function isBuiltin(name: string) {
  return FRAME_BUILTINS.some((item) => item.name === name);
}

function warnBuiltin(verb: string, name: string, because: string) {
  if (!import.meta.env.DEV) return;
  console.warn(`[record-page] page.frame.${verb}('${name}') — '${name}' is a built-in region: ${because}.`);
}
