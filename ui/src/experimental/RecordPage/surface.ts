// One customizable region of a Record page. Verbs record ops; the rendered list
// is those ops replayed over the host's built-ins, so a refresh replay and a
// built-in that changed underneath both resolve to the same answer.
import { reactive } from "vue";
import { runningSource } from "./context";
import { ensureIcons } from "./iconClasses";
import type { Position, SurfaceItem, SurfaceVerbs } from "./types";

export interface ResolvedItem<Item extends SurfaceItem = SurfaceItem> {
	item: Item;
	source: string;
	hidden: boolean;
}

type Op<Item extends SurfaceItem> =
	| { verb: "add"; source: string; item: Item; position?: Position }
	| { verb: "hide" | "show"; source: string; name: string }
	| { verb: "update"; source: string; name: string; patch: Partial<Item> }
	| { verb: "move"; source: string; name: string; position: Position }
	| { verb: "order"; source: string; names: string[] };

export const BUILTIN = "builtin";

export class Surface<Item extends SurfaceItem = SurfaceItem> implements SurfaceVerbs<Item> {
	private ops: Op<Item>[] = reactive([]);
	private builtins: () => Item[] = () => [];

	add(item: Item, position?: Position) {
		ensureIcons(item);
		this.ops.push({ verb: "add", source: runningSource(), item, position });
	}

	hide(name: string) {
		this.ops.push({ verb: "hide", source: runningSource(), name });
	}

	show(name: string) {
		this.ops.push({ verb: "show", source: runningSource(), name });
	}

	update(name: string, patch: Partial<Item>) {
		ensureIcons(patch);
		this.ops.push({ verb: "update", source: runningSource(), name, patch });
	}

	move(name: string, position: Position) {
		this.ops.push({ verb: "move", source: runningSource(), name, position });
	}

	order(names: string[]) {
		this.ops.push({ verb: "order", source: runningSource(), names });
	}

	has(name: string) {
		return this.resolve().some((entry) => entry.item.name === name);
	}

	// Host side, below: not part of what a script may call.

	provideBuiltins(get: () => Item[]) {
		this.builtins = get;
	}

	/** The replay clear: the next resolve starts from built-ins alone. */
	reset() {
		this.ops.length = 0;
	}

	resolve(): ResolvedItem<Item>[] {
		const items = this.builtins().map((item) => ({
			item: { ...item },
			source: BUILTIN,
			hidden: false,
		}));
		for (const op of this.ops) apply(items, op);
		return items;
	}

	visible(): Item[] {
		return this.resolve()
			.filter((entry) => !entry.hidden)
			.map((entry) => entry.item);
	}
}

function apply<Item extends SurfaceItem>(items: ResolvedItem<Item>[], op: Op<Item>) {
	if (op.verb === "add") return add(items, op);
	if (op.verb === "order") return order(items, op.names);
	const found = items.find((entry) => entry.item.name === op.name);
	if (!found) return;
	if (op.verb === "hide") found.hidden = true;
	if (op.verb === "show") found.hidden = false;
	if (op.verb === "update") Object.assign(found.item, op.patch);
	if (op.verb === "move") reposition(items, found, op.position);
}

// A name collision replaces in place and transfers ownership; the earlier item
// keeps its slot unless the writer also asked for a position.
function add<Item extends SurfaceItem>(
	items: ResolvedItem<Item>[],
	op: { source: string; item: Item; position?: Position },
) {
	const entry = { item: { ...op.item }, source: op.source, hidden: false };
	const existing = items.find((candidate) => candidate.item.name === op.item.name);
	if (existing) {
		warnCollision(existing, op);
		items[items.indexOf(existing)] = entry;
		if (op.position) reposition(items, entry, op.position);
		return;
	}
	items.splice(anchorIndex(items, op.position), 0, entry);
}

function reposition<Item extends SurfaceItem>(
	items: ResolvedItem<Item>[],
	entry: ResolvedItem<Item>,
	position: Position,
) {
	items.splice(items.indexOf(entry), 1);
	items.splice(anchorIndex(items, position), 0, entry);
}

// An absent anchor degrades to append, so a guest never fails on an unknown name.
function anchorIndex<Item extends SurfaceItem>(items: ResolvedItem<Item>[], position?: Position) {
	if (!position) return items.length;
	const target = items.findIndex(
		(entry) => entry.item.name === (position.before ?? position.after),
	);
	if (target === -1) return items.length;
	return position.before ? target : target + 1;
}

// Listed-and-present names to the front in the given sequence; unlisted items
// follow in their prior relative order; unknown names are skipped.
function order<Item extends SurfaceItem>(items: ResolvedItem<Item>[], names: string[]) {
	const rank = (entry: ResolvedItem<Item>) => {
		const claimed = names.indexOf(entry.item.name);
		return claimed === -1 ? names.length : claimed;
	};
	const arranged = items
		.map((entry, position) => ({ entry, position }))
		.sort((a, b) => rank(a.entry) - rank(b.entry) || a.position - b.position)
		.map(({ entry }) => entry);
	items.splice(0, items.length, ...arranged);
}

function warnCollision(existing: ResolvedItem<any>, op: { source: string; item: SurfaceItem }) {
	if (!import.meta.env.DEV) return;
	if (existing.source === op.source) return;
	console.warn(
		`[record-page] '${op.item.name}' from ${existing.source} overwritten by ${op.source}`,
	);
}
