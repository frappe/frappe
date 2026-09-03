// What sidebar this tab last resolved for an address. `sessionStorage`, so the unit is the
// TAB: a second tab resolves off the address again.

const KEY = "frappe:desk:sidebar";

// Every address that opens a sidebar is recorded and records get their own, so an uncapped
// record grows for the life of the tab and every navigation re-serialises all of it.
const KEEP = 100;

/** The whole record, or an empty one. */
function read(): Record<string, string> {
	try {
		const raw = sessionStorage.getItem(KEY);
		const parsed = raw ? JSON.parse(raw) : null;
		return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
	} catch {
		// Storage throws on access in a sandboxed frame and at zero quota. A tab that cannot
		// remember resolves off the address, which is never wrong, only less continuous.
		return {};
	}
}

/** The sidebar this tab last resolved for `path`, if it remembers one. */
export function recallSidebar(path: string): string | undefined {
	const remembered = read()[path];
	return typeof remembered === "string" ? remembered : undefined;
}

/** Record `sidebar` as the answer for `path`, called when a push resolves one. */
export function rememberSidebar(path: string, sidebar: string): void {
	const record = read();
	if (record[path] === sidebar) return;

	// Re-insertion keeps key order least-recent first, so the cap below evicts the address
	// that has gone longest without resolving.
	delete record[path];
	record[path] = sidebar;

	const addresses = Object.keys(record);
	for (const stale of addresses.slice(0, Math.max(0, addresses.length - KEEP))) {
		delete record[stale];
	}

	try {
		sessionStorage.setItem(KEY, JSON.stringify(record));
	} catch {
		// Full or forbidden. The sidebar still resolves; it will not survive a reload.
	}
}
