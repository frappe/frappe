// The palette's own search: no fuzzy matching, three tiers, then recency, then the alphabet.
import { matchTier } from "./matchTier";
import type { PaletteRow } from "./palette";
import { recents } from "./recents";

const MISS = 3;

/** The rows that match `query`, best first; the hidden keywords rank as the label does. */
export function rank(rows: PaletteRow[], query: string): PaletteRow[] {
	const needle = query.trim().toLowerCase();
	if (!needle) return rows;
	return rows
		.map((row) => ({ row, tier: tierOf(row, needle), recency: recencyOf(row) }))
		.filter(({ tier }) => tier < MISS)
		.sort(
			(a, b) =>
				a.tier - b.tier ||
				compareRecency(a.recency, b.recency) ||
				a.row.label.localeCompare(b.row.label)
		)
		.map(({ row }) => row);
}

function tierOf(row: PaletteRow, needle: string): number {
	const tiers = [row.label, ...(row.keywords ?? [])].map((text) => matchTier(text, needle) ?? MISS);
	return Math.min(...tiers);
}

function recencyOf(row: PaletteRow) {
	return row.href ? recents.recency(row.href) : Infinity;
}

// Two rows never opened tie here, and `Infinity - Infinity` would not.
function compareRecency(a: number, b: number) {
	return a === b ? 0 : a < b ? -1 : 1;
}
