// The one act dispatcher: it runs an act by its full name, `<surface>.<item>`, whoever asks.
// A page registers the surfaces it draws; the shell and the list page register theirs the same way.
import { shallowReactive } from "vue";
import { toast } from "frappe-ui";
import { __ } from "@/i18n";
import { loadedText, loadText } from "./actText";
import { checkValue, type ActSchema } from "./schema/checkValue";

/** A ptype on the page's doctype (`"write"`), or one on any doctype. */
export type ActRight = string | { doctype: string; ptype: string };

/** One choice of an act's argument; its `value` reaches `run`. */
export interface ActOption {
	value: unknown;
	label: string;
	description?: string;
	icon?: string;
	/** Draws a round avatar in place of the icon: the picture at this address, or the label's initials when `null`. */
	image?: string | null;
	/** Why the option cannot be picked, such as "Assigned"; drawn on its right. */
	disabled?: string;
}

export interface ActArgument<Context = any> {
	label: string;
	options: (context: Context, query: string) => ActOption[] | Promise<ActOption[]>;
}

/** A dialog an act may open and wait on until the person answers. */
export type ActAsk = "confirm" | "danger" | "dialog" | "picker";

/** The optional fields an item that has `run` carries as an act. */
export interface ActFields<Context = any> {
	/** A default combo in `useKeyboardShortcut` syntax, such as `"Mod+Shift+D"`. */
	key?: string;
	right?: ActRight;
	/** Keeps the act out of the palette; a script and a key still run it. */
	palette?: false;
	argument?: ActArgument<Context>;
	/** Sync and cheap; false keeps the act off every surface. It reads the state the app already holds. */
	when?: (context: Context) => boolean;
	/** What the act does, what it returns, what it asks the person, and when not to use it. */
	description?: string;
	/** The value `run` takes, as `run` gets it; no value counts as `null`. A described act with no `input` takes no value. */
	input?: ActSchema;
	/** The `data` the act resolves with; absent means `null`. */
	output?: ActSchema;
	/** The dialogs the act may wait on. */
	asks?: ActAsk[];
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
	/** A promise while the act `name`, which it does not hold yet, may still load; else nothing. */
	loading?: (name: string) => Promise<void> | undefined;
	/** Whether the act `name`, which it does not hold yet, may still load; reads only reactive state, starts nothing. */
	loads?: (name: string) => boolean;
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

/** The value does not fit the act's `input`; `message` says what to send instead. */
export class ActInvalid extends Error {
	constructor(readonly act: string, message: string) {
		super(`${act}: ${message}`);
		this.name = "ActInvalid";
	}
}

/** The person said no to a confirm the act waited on; nothing ran. */
export class ActDeclined extends Error {
	constructor(readonly act: string) {
		super(`${act}: the person declined`);
		this.name = "ActDeclined";
	}
}

/** An open dialog as `readDialogs` lists it. */
export interface ActDialog {
	id: number;
	kind: "confirm" | "danger" | "form" | "dialog";
	title: string;
	message: string;
	buttons: string[];
	fieldnames?: string[];
	values?: Record<string, any>;
}

export type ActErrorCode =
	| ActDeniedReason
	| "invalid"
	| "failed"
	| "declined"
	| "waiting_for_user"
	| "interrupted";

export interface ActError {
	code: ActErrorCode;
	/** Plain English: what happened and what to do next. */
	message: string;
	dialog?: ActDialog;
}

/** What an outside caller gets from `call`; `route` and `dialogs` are the tab's when the act ended. */
export type ActResult = { route: string; dialogs: ActDialog[] } & (
	| { ok: true; data: unknown }
	| { ok: false; error: ActError }
);

interface Checked {
	scope: ActScope;
	item: ActItem;
}

interface Found {
	scope: ActScope;
	entry: ActEntry;
}

export class ActDispatcher {
	// Each surface name keeps its scopes oldest first; the last one answers.
	private stacks = shallowReactive(new Map<string, ActScope[]>());

	/** A later scope shadows a surface name; letting go of it restores the one it shadowed. */
	register(scope: ActScope): () => void {
		for (const surface of Object.keys(scope.surfaces))
			this.stacks.set(surface, [...(this.stacks.get(surface) ?? []), scope]);
		return () => {
			for (const surface of Object.keys(scope.surfaces)) {
				const rest = (this.stacks.get(surface) ?? []).filter((held) => held !== scope);
				if (rest.length) this.stacks.set(surface, rest);
				else this.stacks.delete(surface);
			}
		};
	}

	private scopeOf(surface: string): ActScope | undefined {
		return this.stacks.get(surface)?.at(-1);
	}

	/** What the scope holding `surface` hands its acts, or undefined while no scope holds it. */
	contextOf(surface: string): unknown {
		return this.scopeOf(surface)?.context();
	}

	/** Every act present, not hidden and allowed now, `palette: false` ones too; `only` narrows them before a right is read. */
	available(only: (item: ActItem) => boolean = () => true): AvailableAct[] {
		const listed: AvailableAct[] = [];
		for (const [surface, held] of this.stacks) {
			const scope = held.at(-1)!;
			for (const entry of scope.surfaces[surface]())
				if (isAct(entry.item) && only(entry.item) && isAvailable(scope, entry))
					listed.push(describe(`${surface}.${entry.item.name}`, entry.item, scope));
		}
		return listed;
	}

	/** `available()` with each act's `description`, `input` and `output` from its surface's sidecar; loads the sidecars it needs. */
	async described(only?: (item: ActItem) => boolean): Promise<AvailableAct[]> {
		const listed = this.available(only);
		await Promise.all([...new Set(listed.map((act) => surfaceOf(act.name)))].map(loadText));
		return listed.map((act) => {
			const text = loadedText(surfaceOf(act.name))?.[nameIn(act.name)];
			return {
				...act,
				description: act.description ?? text?.description,
				input: act.input ?? text?.input,
				output: act.output ?? text?.output,
			};
		});
	}

	/** The acts the palette's first step lists: a label, and not `palette: false`. The navigation picker asks the same. */
	listed(): AvailableAct[] {
		return this.available().filter((act) => act.palette !== false && !!act.label);
	}

	/** One act by its full name while `available()` would list it; reads only its own surface. */
	find(name: string): AvailableAct | undefined {
		const found = this.lookup(name);
		if (!found || !isAvailable(found.scope, found.entry)) return undefined;
		return describe(name, found.entry.item, found.scope);
	}

	/** Whether `name` is not held yet but its scope is still loading acts; for a row that draws before they arrive. */
	loads(name: string): boolean {
		return !this.lookup(name) && !!this.scopeOf(surfaceOf(name))?.loads?.(name);
	}

	/** A promise while `name` may still load or its right still settle (it starts them), so `find` can answer; else nothing. */
	ready(name: string): Promise<void> | undefined {
		const found = this.lookup(name);
		const loading = found ? undefined : this.scopeOf(surfaceOf(name))?.loading?.(name);
		if (loading) return loading.then(() => this.ready(name));

		const right = found?.entry.item.right;
		return right ? found!.scope.settled(right) : undefined;
	}

	/** Runs the act inside its scope's hold; rejects with `ActDenied`, `ActInvalid`, or what the act threw. A script's `run` resolves nothing when the person declines. */
	run(name: string, value?: unknown): Promise<unknown> {
		return this.execute(name, value, true);
	}

	/** An outside caller's run: it never rejects, and every end, a refusal too, says what to do next. */
	call(name: string, value?: unknown): Promise<ActResult> {
		const run = this.execute(name, value, false);
		// A refusal that lands before the chunk does must not count as unhandled; `callResult` reads it.
		run.catch(() => {});
		// The act starts at once, on the page that was asked; only the result's wording loads on the first call. A failed load must not reject it.
		return import("./callResult").then(
			({ callResult }) => callResult(run, name, readDialogs),
			(error): ActResult => ({ ok: false, error: { code: "failed", message: String(error) }, route: "", dialogs: [] })
		);
	}

	private async execute(name: string, value: unknown, quiet: boolean): Promise<unknown> {
		const checked = this.check(name, value, true);
		const { scope, item } = checked instanceof Promise ? await checked : checked;
		const held = scope.hold(() => item.run!(scope.context(), value));
		return quiet ? held.catch(ignoreDeclined) : held;
	}

	/** Runs an act the reader asked for, by a click, the palette or a key; it never rejects. */
	async perform(name: string, value?: unknown): Promise<void> {
		let checked: Checked;
		try {
			// A click starts its act in its own tick: it waits on a sidecar only to check a value it carries.
			const pending = this.check(name, value, value !== undefined);
			checked = pending instanceof Promise ? await pending : pending;
		} catch (error) {
			return void toast.error(deniedMessage(error as Error));
		}
		const { scope, item } = checked;
		try {
			await scope.hold(() => item.run!(scope.context(), value));
		} catch (error) {
			if (!(error instanceof ActDeclined)) await scope.failed(error);
		}
	}

	// Synchronous unless a right must settle, the act still loads or its sidecar must load, so a click's act starts in the click's own tick.
	private check(name: string, value: unknown, wait: boolean): Checked | Promise<Checked> {
		const permitted = this.permit(name);
		if (permitted instanceof Promise) return permitted.then((checked) => this.valid(name, checked, value, wait));
		return this.valid(name, permitted, value, wait);
	}

	private permit(name: string): Checked | Promise<Checked> {
		const found = this.lookup(name);
		const loading = found ? undefined : this.scopeOf(surfaceOf(name))?.loading?.(name);
		if (loading) return loading.then(() => this.permit(name));
		const right = found?.entry.item.right;
		const settling = found && right ? found.scope.settled(right) : undefined;
		if (settling) return settling.then(() => this.allowed(name, this.sameScope(name, found)));
		return this.allowed(name, found);
	}

	// An act with no declaration, inline or in its sidecar, takes any value: a script's act may leave them out.
	private valid(name: string, checked: Checked, value: unknown, wait: boolean): Checked | Promise<Checked> {
		const { item } = checked;
		const surface = surfaceOf(name);
		if (item.input === undefined && !loadedText(surface)) {
			const loading = loadText(surface);
			return wait ? loading.then(() => this.valid(name, this.allowed(name, this.sameScope(name, checked)), value, wait)) : checked;
		}
		const text = loadedText(surface)?.[nameIn(name)];
		const schema = item.input ?? text?.input;
		if (schema) refuse(name, checkValue(schema, value ?? null));
		else if ((item.description ?? text) && !item.argument) refuse(name, takesNothing(value));
		return checked;
	}

	// A page that replaced the asking one while the right settled holds a different act of the same name.
	private sameScope(name: string, asked: Pick<Found, "scope"> | null) {
		const found = this.lookup(name);
		return found && found.scope === asked?.scope ? found : null;
	}

	private allowed(name: string, found: Found | null): Checked {
		if (!found) throw new ActDenied(name, "missing");
		const { scope, entry } = found;
		if (entry.hidden) throw new ActDenied(name, "hidden");
		if (!passesWhen(scope, entry.item)) throw new ActDenied(name, "hidden");
		if (!passesRight(scope, entry.item)) throw new ActDenied(name, "right");
		return { scope, item: entry.item };
	}

	private lookup(name: string): Found | null {
		const surface = surfaceOf(name);
		const scope = this.scopeOf(surface);
		if (!scope) return null;
		const item = name.slice(surface.length + 1);
		const entry = scope.surfaces[surface]().find(
			(candidate) => candidate.item.name === item && isAct(candidate.item)
		);
		return entry ? { scope, entry } : null;
	}
}

/** Whether the item's right has settled and passes: a surface draws an item only while it does. */
export function passesRight(
	scope: Pick<ActScope, "passes" | "settled">,
	{ right }: ActFields
): boolean {
	return !right || (!scope.settled(right) && scope.passes(right));
}

/** Whether the item's `when` holds for the scope's context; a throwing `when` hides its act. */
export function passesWhen(scope: Pick<ActScope, "context">, { when }: ActFields): boolean {
	if (when === undefined) return true;
	try {
		return when(scope.context());
	} catch (error) {
		console.error("[frappe] An act's `when` threw; the act is hidden.", error);
		return false;
	}
}

/** The desk's one dispatcher. */
export const acts = new ActDispatcher();

function ignoreDeclined(error: unknown) {
	if (!(error instanceof ActDeclined)) throw error;
}

let readDialogs: () => ActDialog[] = () => [];

/** The tab's dialog list registers its reader here: the acts layer sits below the shell's. */
export function readDialogsWith(reader: () => ActDialog[]) {
	readDialogs = reader;
}

function nameIn(name: string) {
	return name.slice(surfaceOf(name).length + 1);
}

function refuse(name: string, reason: string | undefined) {
	if (reason) throw new ActInvalid(name, reason);
}

function takesNothing(value: unknown) {
	return value === undefined || value === null ? undefined : "this act takes no value; send none";
}

function surfaceOf(name: string) {
	const dot = name.indexOf(".");
	return dot > 0 ? name.slice(0, dot) : "";
}

function isAct(item: ActItem) {
	return typeof item.run === "function";
}

function isAvailable(scope: ActScope, { item, hidden }: ActEntry) {
	return !hidden && passesWhen(scope, item) && passesRight(scope, item);
}

function describe(name: string, item: ActItem, scope: ActScope): AvailableAct {
	const { label, icon, key, right, palette, argument, description, input, output, asks } = item;
	const act: AvailableAct = { name, label, icon, key, right, palette, description, input, output, asks };
	if (argument)
		act.argument = {
			label: argument.label,
			options: (query) => argument.options(scope.context(), query),
		};
	return act;
}

function deniedMessage(error: Error) {
	if (error instanceof ActInvalid) return error.message;
	if (!(error instanceof ActDenied)) return __("This act could not be checked. Reload the page and try again.");
	return (error as ActDenied).reason === "right"
		? __("You do not have permission to do this")
		: __("This is not available on this page now");
}
