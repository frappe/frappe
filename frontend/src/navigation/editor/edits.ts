// What a person can do to the draft. Each edit returns the next draft or a refusal string:
// nothing throws, and a refusal is shown under its field, never as a toast.

import { __ } from "@/i18n";
import { canNestUnder } from "../nesting";
import { type Draft, type EditorRow, isOwn, RAIL, rowsOf, withRows } from "./draft";

export type Edited = Draft | string;

export function refused(edited: Edited): edited is string {
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
