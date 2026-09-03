// What panel this tab was last in, per address (#42464).
//
// The first thing the desk v2 shell stores. It narrows charter point 7 on purpose, and the
// narrowing is exactly this wide: the record NEVER invents a panel and never beats a deeper
// cover. It only ever picks among panels the address itself already allows, all of which are
// equally correct answers to it (#42432). So a cold load in a fresh tab is still a pure
// function of the address, and two colleagues opening one URL get one shell.
//
// `sessionStorage`, not `localStorage`, because the unit is the TAB. A reload and the back
// button keep the panel, which is the whole point; a second tab on the same address starts
// from the address again, which is what makes the cold load still mean something. Outliving
// the tab would make the canonical panel unreachable without clearing site data.
//
// Keyed by path alone. The panel is a fact about which rows cover this address, and the query
// is context rather than identity (#42102) — `?view=` and `?tab=` move you inside a list, not
// into another panel, so hanging a separate record off each of them would only make the
// panel flicker as you switch views.

const KEY = "frappe:desk:panel";

/**
 * The whole record, or an empty one.
 *
 * Every read goes through here rather than caching, because `sessionStorage` is shared with
 * anything else on the tab and this is a handful of short strings read once per navigation.
 * Storage throws in more places than it looks — Safari's private mode has historically thrown
 * on WRITE with a zero quota, and a sandboxed frame throws on ACCESS — so both sides swallow.
 * A tab that cannot remember its panel falls back to resolving off the address, which is the
 * behaviour that shipped before this and is never wrong, only less continuous.
 */
function read(): Record<string, string> {
	try {
		const raw = sessionStorage.getItem(KEY);
		const parsed = raw ? JSON.parse(raw) : null;
		// Anything but an object of strings is someone else's data or a half-written value.
		return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
	} catch {
		return {};
	}
}

/** The panel this tab last resolved for `path`, if it remembers one. */
export function recallPanel(path: string): string | undefined {
	const remembered = read()[path];
	return typeof remembered === "string" ? remembered : undefined;
}

/**
 * Record `panel` as the answer for `path`.
 *
 * Called when the panel RESOLVES, not when a row is clicked. Rows are plain `RouterLink`s
 * (`NavigationRow.vue`) and Vue Router's `RouterLink` cannot carry history state, so anything
 * hung off the click would have cost the plain link and broken middle-click and
 * open-in-new-tab. Resolution happens on every arrival however you got there — click, paste,
 * reload, back — so this is the one hook that catches all of them.
 */
export function rememberPanel(path: string, panel: string): void {
	const record = read();
	if (record[path] === panel) return;

	record[path] = panel;
	try {
		sessionStorage.setItem(KEY, JSON.stringify(record));
	} catch {
		// Full or forbidden. The panel still resolves; it just will not survive a reload.
	}
}
