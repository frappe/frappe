// Which sections a reader has opened or shut for themselves. `localStorage`, so the unit is
// the BROWSER — and keyed by user, because a browser profile is shared and a disclosure is not.

import { browserMemory } from "@/browserMemory";
import type { NavigationItem } from "@/boot";

/** One reader's toggles for one container: section key to open. */
type Sections = Record<string, boolean>;
type Containers = Record<string, Sections>;

export type SectionMemory = {
	/** What this reader decided about `key`, or nothing if they have not decided. */
	recall(key: string): boolean | undefined;
	/** Record a click on `key`'s heading. */
	remember(key: string, open: boolean): void;
};

/**
 * This reader's disclosures for one container, read once and pruned against what it ships.
 */
export function sectionMemory(
	user: string,
	container: string,
	items: Pick<NavigationItem, "key" | "keep_closed">[]
): SectionMemory {
	const memory = browserMemory("sections", user, isContainers);
	const shippedOpen = new Map(items.map((item) => [item.key, !item.keep_closed]));

	const kept: Sections = {};

	for (const [key, open] of Object.entries(memory.recall()?.[container] ?? {})) {
		// `has`, not truthiness on `get`: a section that is gone and one that ships shut
		// both answer falsey, and only the first is stale.
		if (!shippedOpen.has(key) || typeof open !== "boolean") continue;
		if (open !== shippedOpen.get(key)) kept[key] = open;
	}

	/** Re-reads, so a write here cannot drop another container's entry. */
	function save() {
		const containers = { ...memory.recall(), [container]: kept };
		if (!Object.keys(kept).length) delete containers[container];
		memory.remember(containers);
	}

	return {
		recall(key) {
			return kept[key];
		},

		remember(key, open) {
			// Back to what the app ships is a decision to forget.
			if (open === shippedOpen.get(key)) delete kept[key];
			else kept[key] = open;

			save();
		},
	};
}

function isContainers(value: unknown): value is Containers {
	return !!value && typeof value === "object" && !Array.isArray(value);
}
