// The editor's copy of one app at one level: the rail, every sidebar and the layout. Pure, so
// vitest covers it without a component.

import type { Arrangements, Defaults, EditorRow, Origin, Payload, Scope } from "@/arrangement";

/** The container id of the rail; a sidebar's id is its address or key, which never starts with a colon. */
export const RAIL = ":rail";

export type { Arrangements, Defaults, EditorRow, Origin, Payload, Scope };

export type Draft = {
	rail: EditorRow[];
	sidebars: Record<string, EditorRow[]>;
	/** This level's own layout; blank follows the level below. */
	layout: string;
	/** The level the draft is saved at: its own rows are the ones added at it. */
	scope: Scope;
};

const MARKERS = ["hidden_by", "no_access", "view_deleted"] as const;

export function fromArrangements(response: Arrangements, scope: Scope): Draft {
	return {
		rail: response.rail,
		sidebars: response.sidebars,
		layout: response.navigation_layouts[scope] ?? "",
		scope,
	};
}

export function rowsOf(draft: Draft, container: string): EditorRow[] {
	return container === RAIL ? draft.rail : draft.sidebars[container] ?? [];
}

/** The draft with one container's rows replaced. */
export function withRows(draft: Draft, container: string, rows: EditorRow[]): Draft {
	if (container === RAIL) return { ...draft, rail: rows };
	return { ...draft, sidebars: { ...draft.sidebars, [container]: rows } };
}

/** The rail row that opens a sidebar, if one in the draft does. */
export function openerOf(draft: Draft, key: string): EditorRow | undefined {
	return draft.rail.find(
		(row) => row.opens_sidebar === key || (row.item_type === "Sidebar" && row.link_to === key)
	);
}

/** The sidebar a rail row opens, if it opens one. */
export function sidebarOf(row: EditorRow | undefined): string | undefined {
	return row?.opens_sidebar ?? (row?.item_type === "Sidebar" ? row.link_to : undefined);
}

/** The sidebars a rail row opens: the only ones the editor offers a tab for. */
export function openedSidebars(draft: Draft): string[] {
	return Object.keys(draft.sidebars).filter((key) => openerOf(draft, key));
}

export function containersOf(draft: Draft): string[] {
	return [RAIL, ...Object.keys(draft.sidebars)];
}

/** Whether rows differ from the opened copy: markers and key order do not count. */
export function rowsChanged(opened: EditorRow[], rows: EditorRow[]): boolean {
	return canonical(opened) !== canonical(rows);
}

export function layoutChanged(opened: Draft, draft: Draft): boolean {
	return opened.layout !== draft.layout;
}

export function dirty(opened: Draft, draft: Draft): boolean {
	return layoutChanged(opened, draft) || changedContainers(opened, draft).length > 0;
}

/** The draft is immutable, so the opened copy is the revert. */
export function revert(opened: Draft): Draft {
	return opened;
}

/** The containers whose rows differ from the opened copy; the rail first. */
export function changedContainers(opened: Draft, draft: Draft): string[] {
	return containersOf(draft).filter(
		(container) => rowsChanged(rowsOf(opened, container), rowsOf(draft, container))
	);
}

/** The changed containers only; markers are dropped, as the save would drop them. */
export function toPayload(opened: Draft, draft: Draft): Payload {
	const payload: Payload = {};
	for (const container of changedContainers(opened, draft)) {
		const rows = rowsOf(draft, container).map(unmarked);
		if (container === RAIL) payload.rail = rows;
		else payload.sidebars = { ...payload.sidebars, [container]: rows };
	}
	return payload;
}

/**
 * Rows go back to the level below: own rows and own sidebars are gone, hidden flags are
 * cleared and the layout follows the level below. `below` is that level's rows.
 */
export function resetToDefault(draft: Draft, below: Defaults): Draft {
	const sidebars: Draft["sidebars"] = {};
	for (const container of Object.keys(draft.sidebars)) {
		if (container in below.sidebars) sidebars[container] = below.sidebars[container];
	}
	return { rail: below.rail, sidebars, layout: "", scope: draft.scope };
}

/** Whether the draft's level added the row; a row added at a level below is inherited, as an app's is. */
export function isOwn(key: string, scope: Scope): boolean {
	return originOf(key) === scope;
}

/** Where a row was added, read from its key: `user:` and `site:` are reserved. */
export function originOf(key: string): Origin {
	if (key.startsWith("user:")) return "user";
	if (key.startsWith("site:")) return "site";
	return "app";
}

/** A new own row's or sidebar's key: the scope, a colon and six base36 characters. */
export function newKey(scope: Scope): string {
	const bytes = crypto.getRandomValues(new Uint8Array(6));
	return `${scope}:${Array.from(bytes, (byte) => (byte % 36).toString(36)).join("")}`;
}

export function unmarked(row: EditorRow): EditorRow {
	const copy = { ...row };
	for (const marker of MARKERS) delete copy[marker];
	return copy;
}

function canonical(rows: EditorRow[]): string {
	return JSON.stringify(
		rows.map((row) => {
			const plain = unmarked(row) as Record<string, unknown>;
			return Object.keys(plain)
				.filter((field) => plain[field] !== undefined)
				.sort()
				.map((field) => [field, plain[field]]);
		})
	);
}
