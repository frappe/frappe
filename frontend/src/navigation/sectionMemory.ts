// Which sections a reader has opened or shut for themselves. `localStorage`, so the unit is
// the BROWSER — and keyed by user, because a browser profile is shared and a disclosure is not.

import type { NavigationItem } from "@/boot";

const KEY = "frappe:desk:sections";

/** One reader's toggles for one container: section key to open. */
type Sections = Record<string, boolean>;
type Stored = Record<string, Record<string, Sections>>;

export type SectionMemory = {
	/** What this reader decided about `key`, or nothing if they have not decided. */
	recall(key: string): boolean | undefined;
	/** Record a click on `key`'s heading. */
	remember(key: string, open: boolean): void;
};

function read(): Stored {
	try {
		const raw = localStorage.getItem(KEY);
		const parsed = raw ? JSON.parse(raw) : null;
		return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
	} catch {
		// Storage throws in a sandboxed frame and at zero quota. A browser that cannot
		// remember shows every section as its app ships it.
		return {};
	}
}

function write(stored: Stored): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(stored));
	} catch {
		// Full or forbidden. The section still opens and closes for this page.
	}
}

/**
 * This reader's disclosures for one container (`Rail:crm`, `Sidebar:doctype_crm_lead`), read
 * once and pruned against the `items` that container currently ships.
 */
export function sectionMemory(
	user: string,
	container: string,
	items: NavigationItem[]
): SectionMemory {
	const shippedOpen = new Map(items.map((item) => [item.key, !item.keep_closed]));

	const kept: Sections = {};

	for (const [key, open] of Object.entries(read()[user]?.[container] ?? {})) {
		// `has`, not truthiness on `get`: a section that is gone and one that ships shut
		// both answer falsey, and only the first is stale.
		if (!shippedOpen.has(key) || typeof open !== "boolean") continue;
		if (open !== shippedOpen.get(key)) kept[key] = open;
	}

	/** Re-reads, so a write here cannot drop another container's entry. */
	function save() {
		const stored = read();
		const forUser = { ...stored[user], [container]: kept };
		if (!Object.keys(kept).length) delete forUser[container];

		const next = { ...stored, [user]: forUser };
		// A reader who toggles everything back leaves nothing behind, not an empty shell.
		if (!Object.keys(forUser).length) delete next[user];

		write(next);
	}

	return {
		recall(key) {
			return kept[key];
		},

		remember(key, open) {
			// Back to what the app ships is a decision to forget, and the only way a reader
			// has of clearing one.
			if (open === shippedOpen.get(key)) delete kept[key];
			else kept[key] = open;

			save();
		},
	};
}
