import type { ListColumn } from "./types";

export const CHECKBOX_TRACK = "2rem";
export const MENU_TRACK = "2rem";
const LEADING_AUTO_TRACK = "minmax(0, 2fr)";
const AUTO_TRACK = "minmax(0, 1fr)";

/** The grid tracks: the checkbox column, one per shown column (a draft width wins), then the row menu's. */
export function columnTracks(
  columns: ListColumn[],
  drafts: Record<string, string> = {},
  rowMenu = false
): string[] {
  const tracks = columns.map((column, index) =>
    trackFor(column, drafts[column.fieldname], index)
  );
  if (!tracks.some((track) => track.includes("fr"))) tracks.push(AUTO_TRACK);
  return [CHECKBOX_TRACK, ...tracks, ...(rowMenu ? [MENU_TRACK] : [])];
}

function trackFor(
  column: ListColumn,
  draft: string | undefined,
  index: number
): string {
  const width = draft ?? column.width;
  if (width) return width;
  return index === 0 ? LEADING_AUTO_TRACK : AUTO_TRACK;
}
