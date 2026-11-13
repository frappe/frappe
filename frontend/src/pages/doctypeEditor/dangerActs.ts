// Design mode's Danger zone: acts on the whole saved DocType. Each writes at once, outside the
// pending edits and the undo stack, so it asks about pending edits first, then its dialog.
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { ActItem } from "@/acts/dispatcher";
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
	askKind: (state: EditorState) => Promise<DoctypeKind | null>;
	askName: (state: EditorState) => Promise<string | null>;
	/** The module to move to, or with `standard`, the app module its files go in. */
	askModule: (state: EditorState, standard: boolean) => Promise<string | null>;
	askDelete: (state: EditorState) => Promise<true | null>;
	/** Opens the editor at the DocType's new name. */
	renamed: (name: string) => Promise<unknown>;
	/** Leaves for the DocType list. */
	deleted: () => Promise<unknown>;
	/** Loads the DocType again. */
	reload: () => Promise<unknown>;
}

const ITEMS: { name: DangerAct; label: string; icon: string; run: (host: EditorActsHost, value?: any) => Promise<void> }[] = [
	{ name: "change_kind", label: "Change kind…", icon: "lucide-shapes", run: changeKind },
	{ name: "rename_doctype", label: "Rename DocType…", icon: "lucide-pencil", run: rename },
	{ name: "move_doctype", label: "Move to another module…", icon: "lucide-folder-input", run: (host, value) => move(host, value, false) },
	{ name: "make_standard", label: "Make it standard…", icon: "lucide-package", run: (host, value) => move(host, value, true) },
	{ name: "delete_doctype", label: "Delete DocType…", icon: "lucide-trash-2", run: remove },
];

/** The `danger` surface: shown where its Settings row is. A value, as `{ kind }`, skips the dialog. */
export function dangerItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return ITEMS.map(({ name, label, icon, run }) => ({
		name,
		label: __(label),
		icon,
		when: () => offered(host, name),
		run: (_context, value) => run(host, value),
	}));
}

function offered(host: EditorActsHost, key: DangerAct): boolean {
	const canvas = host.canvas();
	return Boolean(canvas && settingRows(canvas.working.value.settings, host.danger.scope()).some((row) => row.key === key));
}

/** The DocType once pending edits are settled; `null` when the reader kept them. */
async function settled(host: EditorActsHost): Promise<EditorState | null> {
	if (!(await host.danger.settle())) return null;
	return host.canvas()?.state ?? null;
}

async function changeKind(host: EditorActsHost, value?: { kind?: DoctypeKind }) {
	const state = await settled(host);
	const kind = state && (value?.kind ?? (await host.danger.askKind(state)));
	if (!state || !kind) return;
	await held(host, async () => {
		await runMethod(DANGER_METHOD.change_kind, { doctype: state.doctype, kind }, { nullable: true });
		const label = KINDS.find((one) => one.value === kind)?.label ?? kind;
		toast.success(__("{0} is a {1} DocType now.", [state.doctype, __(label)]));
		await host.danger.reload();
	});
}

async function rename(host: EditorActsHost, value?: { name?: string }) {
	const state = await settled(host);
	const asked = state && (value?.name ?? (await host.danger.askName(state)));
	if (!state || !asked) return;
	await held(host, async () => {
		const { data: name } = await runMethod<string>(DANGER_METHOD.rename_doctype, { doctype: state.doctype, new_name: asked });
		toast.success(__("Renamed {0} to {1}.", [state.doctype, name]));
		await host.danger.renamed(name);
	});
}

async function move(host: EditorActsHost, value: { module?: string } | undefined, standard: boolean) {
	const state = await settled(host);
	const module = state && (value?.module ?? (await host.danger.askModule(state, standard)));
	if (!state || !module) return;
	const { doctype } = state;
	await held(host, async () => {
		await runMethod(standard ? DANGER_METHOD.make_standard : DANGER_METHOD.move_doctype, { doctype, module }, { nullable: true });
		toast.success(standard ? __("{0} is standard now, in {1}.", [doctype, module]) : __("Moved {0} to {1}.", [doctype, module]));
		await host.danger.reload();
	});
}

async function remove(host: EditorActsHost) {
	const state = await settled(host);
	if (!state || !(await host.danger.askDelete(state))) return;
	await held(host, async () => {
		await runMethod(DANGER_METHOD.delete_doctype, { doctype: state.doctype }, { nullable: true });
		toast.success(__("Deleted {0}.", [state.doctype]));
		await host.danger.deleted();
	});
}

/** An act holds every edit until it and the page's follow-up finish: the reload drops what is pending. */
async function held(host: EditorActsHost, run: () => Promise<void>) {
	host.edits.locked.value = true;
	try {
		await run();
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
