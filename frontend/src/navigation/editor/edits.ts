// What a person can do to the draft. Each edit returns the next draft or a refusal string:
// nothing throws, and a refusal is shown under its field, never as a toast.

import { __ } from "@/i18n";
import { canNestUnder } from "../nesting";
import {
	type Draft,
	type EditorRow,
	type Scope,
	newKey,
	isOwn,
	openerOf,
	sidebarOf,
	RAIL,
	rowsOf,
	withRows,
} from "./draft";

export type Edited = Draft | string;

export function refused(edited: unknown): edited is string {
	return typeof edited === "string";
}

/** The fields a person may change on an inherited row. */
const INHERITED_FIELDS = ["label", "icon", "opens_sidebar"] as const;

/** An inherited row takes only its label, icon and sidebar; an own row takes every field. */
export function update(
	draft: Draft,
	container: string,
	key: string,
	fields: Partial<EditorRow>
): Edited {
	const row = find(draft, container, key);
	if (!row) return __("This row no longer exists.");

	const allowed = isOwn(key, draft.scope)
		? fields
		: Object.fromEntries(
				INHERITED_FIELDS.filter((field) => field in fields).map((field) => [field, fields[field]])
		  );

	return replace(draft, container, key, (current) => withoutBlanks({ ...current, ...allowed }));
}

/** Hide or show a row; Show also works on a row the site hid. */
export function toggleHidden(draft: Draft, container: string, key: string): Edited {
	if (!find(draft, container, key)) return __("This row no longer exists.");
	return replace(draft, container, key, (row) => {
		const { hidden, ...rest } = row;
		return hidden ? rest : { ...rest, hidden: 1 };
	});
}

/** Place a row under another, or at the top level with a blank parent. */
export function nest(draft: Draft, container: string, key: string, parentKey: string | null): Edited {
	const rows = rowsOf(draft, container);
	const row = rows.find((entry) => entry.key === key);
	if (!row) return __("This row no longer exists.");

	const parent = parentKey ? rows.find((entry) => entry.key === parentKey) ?? null : null;
	if (parentKey && !parent) return __("That parent no longer exists.");
	if (parent && descends(rows, parent, key)) return __("A row cannot sit under its own children.");
	if (!canNestUnder(row, parent, container === RAIL ? "Rail" : "Sidebar", rows)) {
		return __("{0} cannot sit there. A section holds items, and an item holds one more level.", [
			row.label || row.link_to || row.key,
		]);
	}

	if (row.parent_key === parent?.key) return draft;

	const nested = replace(draft, container, key, ({ parent_key, ...rest }) =>
		parent ? { ...rest, parent_key: parent.key } : rest
	);

	// The row lands last in its new group, so it draws under its parent.
	const nestedRows = rowsOf(nested, container);
	const order = [...siblingKeys(nestedRows, parent?.key).filter((entry) => entry !== key), key];
	return withRows(nested, container, flatten(nestedRows, parent?.key, order));
}

/**
 * Move one row to the next sibling's place. Hidden siblings are passed over unless `hiddenShown`,
 * so the row always moves past something the person sees. At the end of its group it stays put.
 */
export function moveAmongSiblings(
	draft: Draft,
	container: string,
	key: string,
	by: 1 | -1,
	hiddenShown = true
): Draft {
	const rows = rowsOf(draft, container);
	const row = rows.find((entry) => entry.key === key);
	if (!row) return draft;

	const group = siblingKeys(rows, row.parent_key);
	const at = group.indexOf(key);
	const isShown = (sibling: string) => hiddenShown || !rows.find((r) => r.key === sibling)?.hidden;

	let to = at + by;
	while (to >= 0 && to < group.length && !isShown(group[to])) to += by;
	if (to < 0 || to >= group.length) return draft;

	const order = group.filter((sibling) => sibling !== key);
	order.splice(to, 0, key);
	return withRows(draft, container, flatten(rows, row.parent_key, order));
}

/** A drop lands before the target, under the target's parent. A row never lands inside itself. */
export function dropBefore(draft: Draft, container: string, key: string, beforeKey: string): Edited {
	const rows = rowsOf(draft, container);
	const row = rows.find((entry) => entry.key === key);
	const target = rows.find((entry) => entry.key === beforeKey);
	if (!row || !target || row === target) return draft;

	const moved = nest(draft, container, key, target.parent_key ?? null);
	if (refused(moved)) return moved;

	const parent = target.parent_key;
	const order = siblingKeys(rowsOf(moved, container), parent).filter((entry) => entry !== key);
	order.splice(order.indexOf(beforeKey), 0, key);
	return withRows(moved, container, flatten(rowsOf(moved, container), parent, order));
}

export const OWN_ROWS_PER_CONTAINER = 50;
export const OWN_ROWS_PER_APP = 100;

export type Moved = { draft: Draft; key: string } | string;

/** Add a row last under `parentKey` (or at the top level); its key must be this level's own. */
export function add(
	draft: Draft,
	container: string,
	row: EditorRow,
	parentKey: string | null,
	scope: Scope
): Edited {
	const capped = overCap(draft, container, 1, scope);
	if (capped) return capped;
	if (container === RAIL && row.item_type === "Section") return __("The rail holds no sections.");

	const rows = rowsOf(draft, container);
	const parent = parentKey ? rows.find((entry) => entry.key === parentKey) ?? null : null;
	if (parentKey && !parent) return __("That parent no longer exists.");
	if (!canNestUnder(row, parent, container === RAIL ? "Rail" : "Sidebar", [...rows, row])) {
		return __("A new row cannot sit there. A section holds items, and an item holds one more level.");
	}

	const added = parent ? { ...row, parent_key: parent.key } : row;
	const order = [...siblingKeys(rows, parent?.key), added.key];
	return withRows(draft, container, flatten([...rows, added], parent?.key, order));
}

/** The rows `remove` deletes with this one: its own descendants. */
export function descendantsToDelete(rows: EditorRow[], key: string, scope: Scope): string[] {
	const gone: string[] = [];
	const visit = (parent: string) => {
		for (const row of rows.filter((entry) => entry.parent_key === parent)) {
			if (!isOwn(row.key, scope)) continue;
			gone.push(row.key);
			visit(row.key);
		}
	};
	visit(key);
	return gone;
}

/**
 * Delete an own row and its own descendants; inherited children are lifted to the top level.
 * A row that opens one of this level's own sidebars takes that sidebar with it.
 */
export function remove(draft: Draft, container: string, key: string, scope: Scope): Edited {
	if (!find(draft, container, key)) return __("This row no longer exists.");
	if (!isOwn(key, scope)) return __("Only a row you added can be deleted. Hide it instead.");

	const rows = rowsOf(draft, container);
	const gone = new Set([key, ...descendantsToDelete(rows, key, scope)]);
	const kept = rows
		.filter((row) => !gone.has(row.key))
		.map((row) => {
			if (!row.parent_key || !gone.has(row.parent_key)) return row;
			const { parent_key, ...lifted } = row;
			return lifted;
		});

	let next = withRows(draft, container, kept);
	for (const row of rows.filter((entry) => gone.has(entry.key))) {
		if (row.opens_sidebar && isOwn(row.opens_sidebar, scope)) next = dropSidebar(next, row.opens_sidebar);
	}
	return next;
}

/**
 * Move a row to the end of another container. An own row keeps its key and fields. An inherited
 * row is hidden in place and an own copy with a new key goes into the target (#47392 R1-Q6).
 * The children come along; a row with children cannot go to the rail.
 */
export function moveTo(draft: Draft, from: string, key: string, to: string, scope: Scope): Moved {
	const rows = rowsOf(draft, from);
	const row = rows.find((entry) => entry.key === key);
	if (!row) return __("This row no longer exists.");
	if (from === to) return { draft, key };

	const family = [row, ...descendantsOf(rows, key)];
	if (to === RAIL && (family.length > 1 || row.item_type === "Section")) {
		return __("{0} cannot go to the rail. The rail is flat and holds no sections.", [labelOf(row)]);
	}

	const copies = family.map((member) => ({ member, key: isOwn(member.key, scope) ? member.key : newKey(scope) }));
	const added = copies.filter(({ member, key }) => key !== member.key).length;
	const capped = overCap(draft, to, copies.length, scope, added);
	if (capped) return capped;

	const rename = new Map(copies.map(({ member, key }) => [member.key, key]));
	const moved = copies.map(({ member, key }): EditorRow => {
		const { hidden, hidden_by, no_access, view_deleted, opens_sidebar, ...rest } = member;
		const own = { ...rest, key } as EditorRow;
		if (member.key === row.key || !member.parent_key) delete own.parent_key;
		else own.parent_key = rename.get(member.parent_key);
		return isOwn(member.key, scope) && opens_sidebar ? { ...own, opens_sidebar } : own;
	});

	// Own rows leave the source; inherited ones stay there, hidden.
	const leaving = new Set(family.filter((member) => isOwn(member.key, scope)).map((member) => member.key));
	const left = rows
		.filter((entry) => !leaving.has(entry.key))
		.map((entry) => (family.includes(entry) && !isOwn(entry.key, scope) ? { ...entry, hidden: 1 as const } : entry));

	const target = rowsOf(draft, to);
	const next = withRows(withRows(draft, from, left), to, [...target, ...moved]);
	return { draft: next, key: rename.get(row.key)! };
}

/** Drop a row before a row of another container, or among the rows of the same one. */
export function dropAcross(
	draft: Draft,
	from: string,
	key: string,
	to: string,
	beforeKey: string,
	scope: Scope
): Moved {
	if (from === to) {
		const dropped = dropBefore(draft, from, key, beforeKey);
		return refused(dropped) ? dropped : { draft: dropped, key };
	}

	const moved = moveTo(draft, from, key, to, scope);
	if (refused(moved)) return moved;
	if (!find(moved.draft, to, beforeKey)) return moved;

	const placed = dropBefore(moved.draft, to, moved.key, beforeKey);
	return refused(placed) ? placed : { draft: placed, key: moved.key };
}

/** A drop onto a rail row that opens a sidebar puts the row at the end of that sidebar (R1-Q9). */
export function dropInto(draft: Draft, from: string, key: string, railKey: string, scope: Scope): Moved {
	const opener = find(draft, RAIL, railKey);
	const sidebar = sidebarOf(opener);
	if (!sidebar || !(sidebar in draft.sidebars)) return __("That row opens no sidebar.");
	if (from === sidebar) return { draft, key };
	return moveTo(draft, from, key, sidebar, scope);
}

/** Whether a rail row can be given a sidebar: it opens none yet. */
export function canGiveSidebar(draft: Draft, row: EditorRow): boolean {
	return row.item_type !== "Sidebar" && !row.opens_sidebar && !openerOf(draft, row.key);
}

/** A new own sidebar whose first row copies the item's target; the item then opens it (#47392 R1-Q3). */
export function giveSidebar(draft: Draft, railKey: string, scope: Scope): Moved {
	const item = find(draft, RAIL, railKey);
	if (!item) return __("This row no longer exists.");
	if (!canGiveSidebar(draft, item)) return __("{0} already opens a sidebar.", [labelOf(item)]);

	const sidebar = newKey(scope);
	const capped = overCap(draft, sidebar, 1, scope);
	if (capped) return capped;

	const { key, parent_key, opens_sidebar, hidden, hidden_by, no_access, view_deleted, ...target } = item;
	const first = { ...target, key: newKey(scope) } as EditorRow;
	const opened = replace(draft, RAIL, railKey, (row) => ({ ...row, opens_sidebar: sidebar }));
	return { draft: { ...opened, sidebars: { ...opened.sidebars, [sidebar]: [first] } }, key: first.key };
}

/** Clear the row's `opens_sidebar` and drop that sidebar; offered for the level's own sidebar only. */
export function removeSidebar(draft: Draft, railKey: string, scope: Scope): Edited {
	const item = find(draft, RAIL, railKey);
	if (!item?.opens_sidebar) return __("This row opens no sidebar.");
	if (!isOwn(item.opens_sidebar, scope)) return __("Only a sidebar you added can be removed.");

	const { opens_sidebar, ...rest } = item;
	return dropSidebar(replace(draft, RAIL, railKey, () => rest), item.opens_sidebar);
}

function dropSidebar(draft: Draft, sidebar: string): Draft {
	const { [sidebar]: dropped, ...sidebars } = draft.sidebars;
	return { ...draft, sidebars };
}

/** The refusal when adding `count` rows to `container` passes a cap; `added` counts only new own rows. */
function overCap(
	draft: Draft,
	container: string,
	count: number,
	scope: Scope,
	added = count
): string | undefined {
	const own = (rows: EditorRow[]) => rows.filter((row) => isOwn(row.key, scope)).length;
	const inContainer = own(rowsOf(draft, container));
	if (inContainer + count > OWN_ROWS_PER_CONTAINER) {
		return __("You can add up to {0} items here.", [OWN_ROWS_PER_CONTAINER]);
	}

	const inApp = own(draft.rail) + Object.values(draft.sidebars).reduce((sum, rows) => sum + own(rows), 0);
	if (inApp + added > OWN_ROWS_PER_APP) {
		return __("You can add up to {0} items to this app, over its rail and all its sidebars.", [
			OWN_ROWS_PER_APP,
		]);
	}
}

function descendantsOf(rows: EditorRow[], key: string): EditorRow[] {
	return rows
		.filter((row) => row.parent_key === key)
		.flatMap((child) => [child, ...descendantsOf(rows, child.key)]);
}

function labelOf(row: EditorRow): string {
	return row.label || row.link_to || row.key;
}

export function find(draft: Draft, container: string, key: string): EditorRow | undefined {
	return rowsOf(draft, container).find((row) => row.key === key);
}

function replace(
	draft: Draft,
	container: string,
	key: string,
	change: (row: EditorRow) => EditorRow
): Draft {
	const rows = rowsOf(draft, container).map((row) => (row.key === key ? change(row) : row));
	return withRows(draft, container, rows);
}

/** A blank label or icon is no value: the row falls back to its kind's. */
function withoutBlanks(row: EditorRow): EditorRow {
	const copy: Record<string, unknown> = { ...row };
	for (const field of ["label", "icon"]) if (copy[field] === "") delete copy[field];
	return copy as EditorRow;
}

function descends(rows: EditorRow[], row: EditorRow, ancestor: string): boolean {
	for (let at: EditorRow | undefined = row; at; at = rows.find((r) => r.key === at!.parent_key)) {
		if (at.key === ancestor) return true;
	}
	return false;
}

function siblingKeys(rows: EditorRow[], parent: string | undefined): string[] {
	return rows.filter((row) => row.parent_key === parent).map((row) => row.key);
}

/**
 * The flat list with one parent's children in `order`, each child still followed by its own
 * descendants. Rows outside that group keep their place.
 */
function flatten(rows: EditorRow[], parent: string | undefined, order: string[]): EditorRow[] {
	const byParent = new Map<string | undefined, EditorRow[]>();
	for (const row of rows) byParent.set(row.parent_key, [...(byParent.get(row.parent_key) ?? []), row]);
	byParent.set(
		parent,
		order.map((key) => rows.find((row) => row.key === key)!)
	);

	const flat: EditorRow[] = [];
	const seen = new Set<string>();
	const walk = (from: string | undefined) => {
		for (const row of byParent.get(from) ?? []) {
			if (seen.has(row.key)) continue;
			seen.add(row.key);
			flat.push(row);
			walk(row.key);
		}
	};
	walk(undefined);

	return [...flat, ...rows.filter((row) => !seen.has(row.key))];
}
