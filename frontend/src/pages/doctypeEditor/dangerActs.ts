// Design mode's Danger zone: acts on the whole saved DocType. Each writes at once, outside the pending edits
// and undo, so it asks about pending edits, then its dialog. An agent's value only fills that dialog in.
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { ActDeclined, type ActAsk, type ActCall, type ActItem } from "@/acts/dispatcher";
import { errorMessage } from "@/recordPage/errorMessage";
import { __, __n } from "@/i18n";
import type { EditorActsHost } from "./editorActs";
import type { EditorState } from "./editorSource";
import { KINDS, settingRows, type DangerScope, type DoctypeKind } from "./settingsRows";

type DangerAct = "change_kind" | "rename_doctype" | "move_doctype" | "make_standard" | "delete_doctype";

export const DANGER_METHOD = Object.fromEntries(
	(["change_kind", "rename_doctype", "move_doctype", "make_standard", "delete_doctype"] as const).map((act) => [
		act,
		`frappe.desk.doctype_editor.danger.${act}`,
	]),
) as Record<DangerAct, string>;

export interface DangerHost {
	/** `null` while a child table opened from the DocType shows: the zone acts on the page's own DocType. */
	scope: () => DangerScope | null;
	/** Save first, Discard or Cancel when edits are pending; true to go on, with none left. */
	settle: () => Promise<boolean>;
	/** Each `ask` sends the act's call through `submit`, stays open on an error and gives `null` when the reader cancels. `initial` fills the dialog for an agent. */
	askKind: (state: EditorState, submit: (kind: DoctypeKind) => Promise<DoctypeKind>, initial?: DoctypeKind) => Promise<DoctypeKind | null>;
	askName: (state: EditorState, submit: (name: string) => Promise<string>, initial?: string) => Promise<string | null>;
	/** The module to move to, or with `standard`, the app module its files go in. */
	askModule: (state: EditorState, standard: boolean, submit: (module: string) => Promise<string>, initial?: string) => Promise<string | null>;
	askDelete: (state: EditorState, submit: () => Promise<true>) => Promise<true | null>;
	/** Opens the editor at the DocType's new name. */
	renamed: (name: string) => Promise<unknown>;
	/** Leaves for the DocType list. */
	deleted: () => Promise<unknown>;
	/** Loads the DocType again. */
	reload: () => Promise<unknown>;
	/** True while the page still shows `doctype`: once the reader leaves, an act skips the page's follow-up. */
	showing: (doctype: string) => boolean;
}

const ITEMS: { name: DangerAct; label: string; icon: string; asks: ActAsk[]; run: (host: EditorActsHost, value?: any, agent?: boolean) => Promise<boolean> }[] = [
	{ name: "change_kind", label: "Change kind…", icon: "lucide-shapes", asks: ["confirm", "dialog"], run: changeKind },
	{ name: "rename_doctype", label: "Rename DocType…", icon: "lucide-pencil", asks: ["confirm", "dialog"], run: rename },
	{ name: "move_doctype", label: "Move to another module…", icon: "lucide-folder-input", asks: ["confirm", "dialog"], run: (host, value, agent) => move(host, value, false, agent) },
	{ name: "make_standard", label: "Make it standard…", icon: "lucide-package", asks: ["confirm", "dialog"], run: (host, value, agent) => move(host, value, true, agent) },
	{ name: "delete_doctype", label: "Delete DocType…", icon: "lucide-trash-2", asks: ["confirm", "danger"], run: remove },
];

/** The `danger` surface: shown where its Settings row is. A person's value, as `{ kind }`, skips the dialog; an agent's fills it in. */
export function dangerItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return ITEMS.map(({ name, label, icon, asks, run }) => ({
		name,
		label: __(label),
		icon,
		asks,
		when: () => offered(host, name),
		run: async (_context, value, call?: ActCall) => {
			const agent = Boolean(call?.agent);
			// A person who cancels ends the act quietly; an agent is told, as `declined`.
			if (!(await run(host, value, agent)) && agent) throw new ActDeclined(`danger.${name}`);
		},
	}));
}

function offered(host: EditorActsHost, key: DangerAct): boolean {
	const canvas = host.canvas();
	// A Save or another act holds the edits: one change to the DocType at a time.
	if (host.edits.locked.value) return false;
	return Boolean(canvas && settingRows(canvas.working.value.settings, host.danger.scope()).some((row) => row.key === key));
}

/** The DocType once pending edits are settled; `null` when the reader kept them. */
async function settled(host: EditorActsHost): Promise<EditorState | null> {
	if (!(await host.danger.settle())) return null;
	return host.canvas()?.state ?? null;
}

async function changeKind(host: EditorActsHost, value?: { kind?: DoctypeKind }, agent = false) {
	const state = await settled(host);
	if (!state) return false;
	return held(host, async () => {
		const call = async (kind: DoctypeKind) => {
			await runMethod(DANGER_METHOD.change_kind, { doctype: state.doctype, kind }, { nullable: true });
			return kind;
		};
		const kind = await answer(value?.kind, agent, call, (submit) => host.danger.askKind(state, submit, value?.kind));
		if (!kind) return false;
		const label = KINDS.find((one) => one.value === kind)?.label ?? kind;
		toast.success(__("{0} is a {1} DocType now.", [state.doctype, __(label)]));
		if (host.danger.showing(state.doctype)) await host.danger.reload();
		return true;
	}, agent);
}

async function rename(host: EditorActsHost, value?: { name?: string }, agent = false) {
	const state = await settled(host);
	if (!state) return false;
	return held(host, async () => {
		const call = async (asked: string) => {
			const { data } = await runMethod<string>(DANGER_METHOD.rename_doctype, { doctype: state.doctype, new_name: asked });
			return data;
		};
		const name = await answer(value?.name, agent, call, (submit) => host.danger.askName(state, submit, value?.name));
		if (!name) return false;
		toast.success(__("Renamed {0} to {1}.", [state.doctype, name]));
		if (host.danger.showing(state.doctype)) await host.danger.renamed(name);
		return true;
	}, agent);
}

async function move(host: EditorActsHost, value: { module?: string } | undefined, standard: boolean, agent = false) {
	const state = await settled(host);
	if (!state) return false;
	const { doctype } = state;
	return held(host, async () => {
		const call = async (module: string) => {
			await runMethod(standard ? DANGER_METHOD.make_standard : DANGER_METHOD.move_doctype, { doctype, module }, { nullable: true });
			return module;
		};
		const module = await answer(value?.module, agent, call, (submit) => host.danger.askModule(state, standard, submit, value?.module));
		if (!module) return false;
		toast.success(standard ? __("{0} is standard now, in {1}.", [doctype, module]) : __("Moved {0} to {1}.", [doctype, module]));
		if (host.danger.showing(doctype)) await host.danger.reload();
		return true;
	}, agent);
}

async function remove(host: EditorActsHost, _value?: unknown, agent = false) {
	const state = await settled(host);
	if (!state) return false;
	return held(host, async () => {
		const call = async () => {
			await runMethod(DANGER_METHOD.delete_doctype, { doctype: state.doctype }, { nullable: true });
			return true as const;
		};
		if (!(await answer<unknown, true>(undefined, false, call, (submit) => host.danger.askDelete(state, () => submit(undefined))))) return false;
		toast.success(__("Deleted {0}.", [state.doctype]));
		if (host.danger.showing(state.doctype)) await host.danger.deleted();
		return true;
	}, agent);
}

/** What the act's call answers: at once for a person's `value`, else through its dialog, which an agent's `value` only fills in. */
async function answer<V, R>(
	value: V | undefined,
	agent: boolean,
	call: (value: V) => Promise<R>,
	ask: (submit: (value: V) => Promise<R>) => Promise<R | null>,
): Promise<R | null> {
	if (value && !agent) return call(value);
	let started = undefined as Promise<R> | undefined;
	let running = false;
	const result = await ask((picked) => {
		running = true;
		started = call(picked);
		started.then(stop, stop);
		return started;
	});
	if (result !== null || !started) return result;
	const lost = running; // the dialog is gone, so a failure now has nowhere to show but a toast
	return started.catch((error) => {
		if (lost) toast.error(errorMessage(error));
		return null;
	});
	function stop() {
		running = false;
	}
}

/** The edits stay locked from the act's dialog opening until it and the page's follow-up finish: the reload drops what is pending. */
async function held(host: EditorActsHost, run: () => Promise<boolean>, agent = false) {
	if (host.edits.locked.value) {
		const busy = __("Another change to this DocType is still running. Try again when it ends.");
		// An agent's call fails, so it never reads a change that did not happen as done.
		if (agent) throw new Error(busy);
		toast.error(busy);
		return true; // nobody declined
	}
	host.edits.locked.value = true;
	try {
		return await run();
	} finally {
		host.edits.locked.value = false;
	}
}

/** Why the Change kind dialog cannot pick `to`; "" when it can. The server counts every row; `records` is what the reader sees. */
export function kindRefusal(doctype: string, from: DoctypeKind, to: DoctypeKind, records: number | null): string {
	if (to === from) return "";
	if (from === "single") return __("A Single keeps its kind. Make a new DocType instead.");
	if (to === "single") return __("Set when a DocType is made. Make a new Single instead.");
	if (!records) return "";
	if (to === "child")
		return __n(
			"Not while {0} has {1} record: a child table's rows need a parent record.",
			"Not while {0} has {1} records: a child table's rows need a parent record.",
			records,
			[doctype, records],
		);
	if (from === "child")
		return __n(
			"Not while {0} has {1} row: its rows belong to parent records.",
			"Not while {0} has {1} rows: its rows belong to parent records.",
			records,
			[doctype, records],
		);
	return "";
}

/** What changing from `from` to `to` does, said under the dialog's list. */
export function kindNotes(doctype: string, from: DoctypeKind, to: DoctypeKind): string[] {
	if (to === from) return [];
	return [
		from === "submittable" && __("Records already submitted stay submitted."),
		from === "tree" && __("The tree fields stay. Remove them in the Editor."),
		from === "child" && __("Adds a System Manager rule, so someone can open the list."),
		to === "submittable" && __("Adds an Amended From field. Submit, Cancel and Amend join the permissions grid."),
		to === "tree" && __("Adds 5 fields: lft, rgt, Is Group, Old Parent and Parent {0}.", [doctype]),
		to === "child" && __("Drops its permissions and Allow import: rows take both from the parent."),
	].filter((note): note is string => Boolean(note));
}
