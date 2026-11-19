// What sidebar this tab last resolved for an address, per user. `sessionStorage`, so the unit
// is the TAB: a second tab resolves off the address again.

import { tabMemory } from "@/browserMemory";

// Uncapped, the record would grow for the life of the tab.
const KEEP = 100;

type Resolved = Record<string, unknown>;

export type SidebarMemory = {
	/** The sidebar this tab last resolved for `path`, if it remembers one. */
	recall(path: string): string | undefined;
	/** Record `sidebar` as the answer for `path`, called when a push resolves one. */
	remember(path: string, sidebar: string): void;
};

/** One reader's address-to-sidebar record in this tab. */
export function sidebarMemory(user: string): SidebarMemory {
	const memory = tabMemory("sidebars", user, isResolved);

	return {
		recall(path) {
			const remembered = memory.recall()?.[path];
			return typeof remembered === "string" ? remembered : undefined;
		},

		remember(path, sidebar) {
			const record = memory.recall() ?? {};
			if (record[path] === sidebar) return;

			// Re-insertion keeps key order least-recent first, so the cap below evicts the address
			// that has gone longest without resolving.
			delete record[path];
			record[path] = sidebar;

			const addresses = Object.keys(record);
			for (const stale of addresses.slice(0, Math.max(0, addresses.length - KEEP))) {
				delete record[stale];
			}

			memory.remember(record);
		},
	};
}

function isResolved(value: unknown): value is Resolved {
	return !!value && typeof value === "object" && !Array.isArray(value);
}
