// The one act dispatcher: it runs an act by its full name, `<surface>.<item>`, whoever asks.
// A page registers the surfaces it draws; the shell and the list page register theirs the same way.
import { shallowReactive } from "vue";
import { toast } from "frappe-ui";
import { __ } from "@/i18n";

/** A ptype on the page's doctype (`"write"`), or one on any doctype. */
export type ActRight = string | { doctype: string; ptype: string };

/** One choice of an act's argument; its `value` reaches `run`. */
export interface ActOption {
	value: unknown;
	label: string;
	description?: string;
}

export interface ActArgument<Context = any> {
	label: string;
	options: (context: Context, query: string) => ActOption[] | Promise<ActOption[]>;
}

/** The optional fields an item that has `run` carries as an act. */
export interface ActFields<Context = any> {
	/** A default combo in `useKeyboardShortcut` syntax, such as `"Mod+Shift+D"`. */
	key?: string;
	right?: ActRight;
	/** Keeps the act out of the palette; a script and a key still run it. */
	palette?: false;
	argument?: ActArgument<Context>;
}

export interface ActItem<Context = any> extends ActFields<Context> {
	name: string;
	label?: string;
	icon?: string;
	run?: (context: Context, value?: any) => unknown;
}

/** One item as its surface draws it after the replay. */
export interface ActEntry {
	item: ActItem;
	hidden: boolean;
}

/** What registers on the dispatcher: a page, or the shell, with the surfaces it draws. */
export interface ActScope<Context = any> {
	/** Each surface's items by the surface's name, the first part of an act's full name. */
	surfaces: Record<string, () => ActEntry[]>;
	/** What `run` and `argument.options` receive. */
	context: () => Context;
	passes: (right: ActRight) => boolean;
	/** A promise while `passes` cannot answer for the right yet; else nothing. */
	settled: (right: ActRight) => Promise<void> | undefined;
	hold: <T>(work: () => T | Promise<T>) => Promise<T>;
	/** An act the reader asked for threw; the scope shows it and recovers. */
	failed: (error: unknown) => void | Promise<void>;
}

/** An act available now, as the palette and the key binder read it. */
export interface AvailableAct extends ActFields {
	/** The full name, `<surface>.<item>`. */
	name: string;
	label?: string;
	icon?: string;
	argument?: {
		label: string;
		options: (query: string) => ActOption[] | Promise<ActOption[]>;
	};
}

export type ActDeniedReason = "missing" | "hidden" | "right";

const DENIALS: Record<ActDeniedReason, string> = {
	missing: "no surface holds this act now",
	hidden: "the act is hidden",
	right: "the user lacks the act's right",
};

/** Why the dispatcher ran nothing: the act is absent, hidden, or its right fails. */
export class ActDenied extends Error {
	constructor(readonly act: string, readonly reason: ActDeniedReason) {
		super(`${act}: ${DENIALS[reason]}`);
		this.name = "ActDenied";
	}
}

interface Checked {
	scope: ActScope;
	item: ActItem;
}

interface Found {
	scope: ActScope;
	entry: ActEntry;
}

export class ActDispatcher {
	private scopes = shallowReactive(new Map<string, ActScope>());

	/** A later scope takes a surface name over; the returned function lets go of only its own. */
	register(scope: ActScope): () => void {
		for (const surface of Object.keys(scope.surfaces)) this.scopes.set(surface, scope);
		return () => {
			for (const surface of Object.keys(scope.surfaces))
				if (this.scopes.get(surface) === scope) this.scopes.delete(surface);
		};
	}

	/** Every act present, not hidden and allowed now, `palette: false` ones too; `only` narrows them before a right is read. */
	available(only: (item: ActItem) => boolean = () => true): AvailableAct[] {
		const listed: AvailableAct[] = [];
		for (const [surface, scope] of this.scopes)
			for (const { item, hidden } of scope.surfaces[surface]())
				if (isAct(item) && !hidden && only(item) && (!item.right || scope.passes(item.right)))
					listed.push(describe(`${surface}.${item.name}`, item, scope));
		return listed;
	}

	/** Runs the act inside its scope's hold; rejects with `ActDenied`, or with what the act threw. */
	async run(name: string, value?: unknown): Promise<unknown> {
		const checked = this.check(name);
		const { scope, item } = checked instanceof Promise ? await checked : checked;
		return scope.hold(() => item.run!(scope.context(), value));
	}

	/** Runs an act the reader asked for, by a click, the palette or a key; it never rejects. */
	async perform(name: string, value?: unknown): Promise<void> {
		let checked: Checked;
		try {
			const pending = this.check(name);
			checked = pending instanceof Promise ? await pending : pending;
		} catch (error) {
			return void toast.error(deniedMessage(error as ActDenied));
		}
		const { scope, item } = checked;
		try {
			await scope.hold(() => item.run!(scope.context(), value));
		} catch (error) {
			await scope.failed(error);
		}
	}

	// Synchronous unless a right must settle, so a click's act starts in the click's own tick.
	private check(name: string): Checked | Promise<Checked> {
		const found = this.lookup(name);
		const right = found?.entry.item.right;
		const settling = found && right ? found.scope.settled(right) : undefined;
		if (settling) return settling.then(() => this.allowed(name, this.sameScope(name, found)));
		return this.allowed(name, found);
	}

	// A page that replaced the asking one while the right settled holds a different act of the same name.
	private sameScope(name: string, asked: Found | null) {
		const found = this.lookup(name);
		return found && found.scope === asked?.scope ? found : null;
	}

	private allowed(name: string, found: Found | null): Checked {
		if (!found) throw new ActDenied(name, "missing");
		const { scope, entry } = found;
		if (entry.hidden) throw new ActDenied(name, "hidden");
		if (entry.item.right && !scope.passes(entry.item.right)) throw new ActDenied(name, "right");
		return { scope, item: entry.item };
	}

	private lookup(name: string): Found | null {
		const dot = name.indexOf(".");
		const scope = dot > 0 ? this.scopes.get(name.slice(0, dot)) : undefined;
		if (!scope) return null;
		const item = name.slice(dot + 1);
		const entry = scope.surfaces[name.slice(0, dot)]().find(
			(candidate) => candidate.item.name === item && isAct(candidate.item)
		);
		return entry ? { scope, entry } : null;
	}
}

/** The desk's one dispatcher. */
export const acts = new ActDispatcher();

function isAct(item: ActItem) {
	return typeof item.run === "function";
}

function describe(name: string, item: ActItem, scope: ActScope): AvailableAct {
	const { label, icon, key, right, palette, argument } = item;
	const act: AvailableAct = { name, label, icon, key, right, palette };
	if (argument)
		act.argument = {
			label: argument.label,
			options: (query) => argument.options(scope.context(), query),
		};
	return act;
}

function deniedMessage(denied: ActDenied) {
	return denied.reason === "right"
		? __("You do not have permission to do this")
		: __("This is not available on this page now");
}
