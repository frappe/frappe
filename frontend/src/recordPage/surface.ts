// One customizable region of a Record page. Verbs record ops; the rendered list
// is those ops replayed over the host's built-ins.
import { markRaw, reactive } from "vue";
import { runningSource } from "./context";
import { ensureIcons } from "./iconClasses";
import { StagedOps } from "./staging";
import type { Position, SurfaceItem, SurfaceVerbs } from "./types";

export interface ResolvedItem<Item extends SurfaceItem = SurfaceItem> {
	item: Item;
	source: string;
	hidden: boolean;
	/** The neighbour the last `add` or `move` named, for a host whose grain the neighbour decides. */
	position?: Position;
}

type Op<Item extends SurfaceItem> =
	| { verb: "add"; source: string; item: Item; position?: Position }
	| { verb: "hide" | "show" | "remove"; source: string; name: string }
	| { verb: "update"; source: string; name: string; patch: Partial<Item> }
	| { verb: "move"; source: string; name: string; position: Position }
	| { verb: "order"; source: string; names: string[] }
	| { verb: "clear"; source: string };

export const BUILTIN = "builtin";

/** The keys a surface reads off an item, and the name its warnings call the surface by. */
export interface Vocabulary {
	surface: string;
	keys: readonly string[];
}

export class Surface<Item extends SurfaceItem = SurfaceItem> implements SurfaceVerbs<Item> {
	private staged = new StagedOps<Op<Item>>(reactive([]));
	private saidKeys = new Set<string>();
	private builtins: () => Item[] = () => [];

	/** Without a vocabulary every key is kept. */
	constructor(private readonly vocabulary?: Vocabulary) {}

	// A block splices as a unit at the anchor: the first item takes the caller's
	// position and each one after it follows the one before.
	add(item: Item | Item[], position?: Position) {
		let anchor = position;
		for (const given of Array.isArray(item) ? item : [item]) {
			const one = this.readKeys("add", given.name, given);
			ensureIcons(one);
			keepComponentRaw(one);
			this.record({ verb: "add", source: runningSource(), item: one, position: anchor });
			anchor = { after: one.name };
		}
	}

	hide(name: string) {
		this.record({ verb: "hide", source: runningSource(), name });
	}

	show(name: string) {
		this.record({ verb: "show", source: runningSource(), name });
	}

	update(name: string, patch: Partial<Item>) {
		const kept = this.readKeys("update", name, patch);
		ensureIcons(kept);
		keepComponentRaw(kept);
		this.record({ verb: "update", source: runningSource(), name, patch: kept });
	}

	move(name: string, position: Position) {
		this.record({ verb: "move", source: runningSource(), name, position });
	}

	order(names: string[]) {
		this.record({ verb: "order", source: runningSource(), names });
	}

	// For a surface whose API names it; `has` answers false once it runs.
	protected remove(name: string) {
		this.record({ verb: "remove", source: runningSource(), name });
	}

	// An op in source order like `hide`, not a reset: items a later source adds are untouched.
	clear() {
		this.record({ verb: "clear", source: runningSource() });
	}

	// Resolves over the replay or hold in flight: a source that calls `add('x')` and then
	// `has('x')` in its own handler is told about its own work.
	has(name: string) {
		return this.fold(this.staged.current).some((entry) => entry.item.name === name);
	}

	// Host side, reading the way `has` reads: `activate` asks this to tell a hidden tab from an absent one.
	isVisible(name: string) {
		return this.fold(this.staged.current).some(
			(entry) => entry.item.name === name && !entry.hidden,
		);
	}

	// Host side, reading the way `has` reads: the item as the replay in flight would render it.
	find(name: string): Item | undefined {
		return this.fold(this.staged.current).find((entry) => entry.item.name === name)?.item;
	}

	// Host side, below: not part of what a script may call.

	provideBuiltins(get: () => Item[]) {
		this.builtins = get;
	}

	/** Opens a replay: ops stage until the last open replay or hold commits. */
	beginReplay() {
		this.staged.beginReplay();
	}

	/** Opens a hold: one handler's ops stage over what is drawn and publish together. */
	beginHold() {
		this.staged.beginHold();
	}

	commitReplay() {
		this.closeStaging();
	}

	commitHold() {
		this.closeStaging();
	}

	/** Draws what has staged so far, less one source's ops, and keeps staging. */
	publishStaged(except?: string) {
		this.staged.publishStaged(except);
	}

	/** The rendered arrangement: committed ops only, never a replay or hold in flight. */
	resolve(): ResolvedItem<Item>[] {
		return this.fold(this.staged.committed);
	}

	visible(): Item[] {
		return this.resolve()
			.filter((entry) => !entry.hidden)
			.map((entry) => entry.item);
	}

	visibleInReplay(): Item[] {
		return this.fold(this.staged.current)
			.filter((entry) => !entry.hidden)
			.map((entry) => entry.item);
	}

	/** True while a replay or a hold is open; acts wait for the commit. */
	protected get staging() {
		return this.staged.isStaging;
	}

	/** True when this closed the last open replay or hold, which publishes. */
	protected closeStaging() {
		return this.staged.commit();
	}

	private record(op: Op<Item>) {
		this.staged.record(op);
	}

	// `has`, `find` and a later `update` must not see a dropped key.
	private readKeys<Given extends Partial<Item>>(verb: string, name: string, given: Given): Given {
		const vocabulary = this.vocabulary;
		if (!vocabulary) return given;
		const kept: Record<string, any> = {};
		for (const key of Object.keys(given)) {
			if (vocabulary.keys.includes(key)) kept[key] = given[key];
			else this.warnUnreadKey(vocabulary.surface, verb, name, key);
		}
		return kept as Given;
	}

	private warnUnreadKey(surface: string, verb: string, name: string, key: string) {
		if (!import.meta.env.DEV) return;
		const once = JSON.stringify([runningSource(), name, key]);
		if (this.saidKeys.has(once)) return;
		this.saidKeys.add(once);
		console.warn(
			`[record-page] ${surface}.${verb}('${name}'): key '${key}' is not one the engine reads — dropped.`,
		);
	}

	private fold(ops: Op<Item>[]): ResolvedItem<Item>[] {
		const items = this.builtins().map((item) => ({
			item: { ...item },
			source: BUILTIN,
			hidden: false,
		}));
		for (const op of ops) apply(items, op);
		return items;
	}
}

// `ops` is reactive, so a component stored on an item, or inside its props, would be
// deep-reactified on its way in, which Vue warns about. Both opt out.
function keepComponentRaw<Item extends SurfaceItem>(item: Partial<Item>) {
	if (item.component) item.component = markRaw(item.component);
	if (item.props) item.props = markRaw({ ...item.props });
}

function apply<Item extends SurfaceItem>(items: ResolvedItem<Item>[], op: Op<Item>) {
	if (op.verb === "add") return add(items, op);
	if (op.verb === "order") return order(items, op.names);
	if (op.verb === "clear") return clear(items);
	const found = items.find((entry) => entry.item.name === op.name);
	if (!found) return;
	if (op.verb === "remove") return void items.splice(items.indexOf(found), 1);
	if (op.verb === "hide") found.hidden = true;
	if (op.verb === "show") found.hidden = false;
	if (op.verb === "update") Object.assign(found.item, op.patch);
	if (op.verb === "move") {
		found.position = op.position;
		reposition(items, found, op.position);
	}
}

// A name collision replaces in place and transfers ownership; the earlier item
// keeps its slot unless the writer also asked for a position.
function add<Item extends SurfaceItem>(
	items: ResolvedItem<Item>[],
	op: { source: string; item: Item; position?: Position },
) {
	const entry: ResolvedItem<Item> = { item: { ...op.item }, source: op.source, hidden: false };
	if (op.position) entry.position = op.position;
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

// Every item present at the call, built-in or added by an earlier source; the items stay addressable.
function clear<Item extends SurfaceItem>(items: ResolvedItem<Item>[]) {
	for (const entry of items) entry.hidden = true;
}

function warnCollision(existing: ResolvedItem<any>, op: { source: string; item: SurfaceItem }) {
	if (!import.meta.env.DEV) return;
	if (existing.source === op.source) return;
	console.warn(
		`[record-page] '${op.item.name}' from ${existing.source} overwritten by ${op.source}`,
	);
}
