// The DocType editor's act surfaces. Every act is `<surface>.<item>` and takes one value.
import { toast } from "frappe-ui";
import { onScopeDispose, type Ref } from "vue";
import { acts, type ActEntry, type ActItem, type ActOption } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { canvasItems, fieldItems } from "./canvasActs";
import { childFieldItems } from "./childActs";
import { customizeItems, modeItems, type CustomizeHost } from "./customizeActs";
import { dangerItems, type DangerHost } from "./dangerActs";
import type { DesignCanvas } from "./designCanvas";
import { EditRefused, type FlatEdit } from "./editorModel";
import type { EditorSave } from "./editorSave";
import { LAYOUT_BREAKS } from "./fieldRules";
import { layoutItems } from "./layoutActs";
import type { EditorTab, PendingEdits } from "./pendingEdits";
import { SECTIONS, settingRows } from "./settingsRows";

export interface EditorActsHost {
	edits: PendingEdits;
	tab: Ref<EditorTab>;
	/** The canvas of the DocType open now; `null` while none has loaded. */
	canvas: () => DesignCanvas | null;
	/** Shows a field, on the canvas or in the tray. */
	find: (fieldname: string) => void;
	/** Opens a setting's section on the Settings tab and flashes its row. */
	findSetting: (key: string) => void;
	/** The record Preview draws, by name; `null` draws an empty form. */
	previewRecord: (name: string | null) => void;
	recordOptions: (query: string) => Promise<ActOption[]>;
	/** The save; its banner's offers decide which of the `editor` save acts show. */
	save: EditorSave;
	/** Opens the saved DocType's list. */
	openList: () => void;
	/** Opens the child table of the parent's Table field, by its fieldname. */
	openChild?: (table: string) => void;
	customize: CustomizeHost;
	danger: DangerHost;
}

export const EDITOR_TABS: { value: EditorTab; label: string }[] = [
	{ value: "editor", label: "Editor" },
	{ value: "settings", label: "Settings" },
	{ value: "preview", label: "Preview" },
];

/** Registers the editor's surfaces for the page's life. */
export function useEditorActs(host: EditorActsHost) {
	const release = acts.register({
		surfaces: {
			editor: () => entries(editorItems(host)),
			canvas: () => entries(canvasItems(host)),
			fields: () => entries([...fieldItems(host), ...childFieldItems(host)]),
			settings: () => entries(settingsItems(host)),
			customize: () => entries(customizeItems(host)),
			danger: () => entries(dangerItems(host)),
			layouts: () => entries(layoutItems(host)),
		},
		context: () => host,
		passes: () => true,
		settled: () => undefined,
		hold: async (work) => work(),
		failed: (error) => void toast.error(refusal(error)),
	});
	onScopeDispose(release);
}

export function editorItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return [...saveItems(host), ...navigationItems(host), ...modeItems(host)];
}

function saveItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const { save } = host;
	return [
		{
			name: "save",
			label: __("Save"),
			icon: "save",
			key: "Mod+S",
			when: () => canSave(host),
			run: () => save.save(),
		},
		{
			name: "reload_and_reapply",
			label: __("Reload and re-apply my edits"),
			icon: "refresh-cw",
			when: () => save.offers("editor.reload_and_reapply"),
			run: () => save.reloadAndReapply(),
		},
		{
			name: "write_files_again",
			label: __("Write files again"),
			icon: "file-output",
			when: () => save.offers("editor.write_files_again"),
			run: () => save.writeFilesAgain(),
		},
		{
			name: "open_list",
			label: __("Open list"),
			icon: "list",
			when: () => hasList(host),
			run: () => host.openList(),
		},
	];
}

/** Save wants edits, or a new DocType, which its first save makes. */
export function canSave(host: Pick<EditorActsHost, "canvas" | "edits" | "save">): boolean {
	const canvas = host.canvas();
	if (!canvas || host.save.saving.value) return false;
	return host.edits.dirty.value || Boolean(canvas.state.pending);
}

function hasList(host: EditorActsHost): boolean {
	const state = host.canvas()?.state;
	return Boolean(state && !state.pending && !state.definition.istable && !state.definition.issingle);
}

function settingsItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return SETTINGS_ACTS.map(([name, label]) => ({
		name,
		label: __(label),
		palette: false,
		when: () => Boolean(host.canvas()),
		run: (_context, keys: Keys | Keys[]) => stageSetting(host.canvas()!, `settings.${name}`, keys),
	}));
}

const SETTINGS_ACTS: [string, string][] = [
	["set_doctype_property", "Set a DocType property"],
	["reset_doctype_property", "Reset a DocType property"],
	["set_naming_series", "Set the naming series"],
	["add_permission", "Add a permission rule"],
	["remove_permission", "Remove a permission rule"],
	["set_permission", "Set a permission"],
	["reset_permissions", "Reset to app permissions"],
];

type Keys = Record<string, unknown>;

/** A list of keys stages as one undo step. The description sits in the header, so its undo stays on the Editor tab. */
function stageSetting(canvas: DesignCanvas, act: string, keys: Keys | Keys[]) {
	const edits: FlatEdit[] = (Array.isArray(keys) ? keys : [keys]).map((one) => ({ ...one, act: settingsAct(one.act) ?? act }));
	if (edits.some((edit) => edit.property === "description")) return canvas.stage(...edits);
	canvas.stageSettings(...edits);
}

/** A key list may name another settings act per key, as picking Naming Series also sets its list. */
function settingsAct(act: unknown) {
	return typeof act === "string" && act.startsWith("settings.") ? act : undefined;
}

function navigationItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return [
		{
			name: "undo",
			label: __("Undo"),
			icon: "corner-up-left",
			key: "Mod+Z",
			// Preview's fields are a real form: there Mod+Z stays the field's own undo.
			when: () => host.tab.value !== "preview" && host.edits.canUndo.value,
			run: () => host.edits.undo(),
		},
		{
			name: "redo",
			label: __("Redo"),
			icon: "corner-up-right",
			key: "Mod+Shift+Z",
			when: () => host.tab.value !== "preview" && host.edits.canRedo.value,
			run: () => host.edits.redo(),
		},
		{
			name: "open_tab",
			label: __("Open tab"),
			argument: {
				label: __("Tab"),
				options: () => EDITOR_TABS.map((tab) => ({ value: tab.value, label: __(tab.label) })),
			},
			run: (_context, tab: EditorTab) => (host.tab.value = tab),
		},
		{
			name: "find",
			label: __("Find a field or setting"),
			icon: "search",
			key: "Mod+J",
			argument: {
				label: __("Field or setting"),
				options: (_context, query) => [...fieldOptions(host, query), ...settingOptions(host, query)],
			},
			run: (_context, found: string | { setting: string }) =>
				typeof found === "string" ? host.find(found) : host.findSetting(found.setting),
		},
		{
			name: "preview_record",
			label: __("Preview a record"),
			argument: { label: __("Record"), options: (_context, query) => host.recordOptions(query) },
			run: (_context, name: string | null) => {
				host.previewRecord(name);
				host.tab.value = "preview";
			},
		},
	];
}

function entries(items: ActItem<EditorActsHost>[]): ActEntry[] {
	return items.map((item) => ({ item, hidden: false }) as ActEntry);
}

function refusal(error: unknown) {
	return error instanceof EditRefused ? __(error.template, error.args) : errorMessage(error);
}

/** Every field of the working state, the ones off the layout marked so. */
function fieldOptions(host: EditorActsHost, query: string): ActOption[] {
	const canvas = host.canvas();
	if (!canvas) return [];
	const off = new Set(canvas.offLayout.value.map(({ field }) => field.fieldname));
	const typed = query.toLowerCase();
	return canvas.working.value.fields
		.filter((field) => !LAYOUT_BREAKS.includes(field.fieldtype))
		.filter((field) => `${field.label ?? ""} ${field.fieldname}`.toLowerCase().includes(typed))
		.map((field) => ({
			value: field.fieldname,
			label: field.label ? __(field.label, [], canvas.state.doctype) : field.fieldname,
			description: off.has(field.fieldname) ? __("Not on this layout") : field.fieldtype,
		}));
}

/** The Settings tab's rows the query matches by label, help or keywords. */
function settingOptions(host: EditorActsHost, query: string): ActOption[] {
	const canvas = host.canvas();
	if (!canvas) return [];
	const typed = query.toLowerCase();
	const sections = new Map(SECTIONS.map((section) => [section.key, section]));
	return settingRows(canvas.working.value.settings, host.danger.scope())
		.filter((row) => [__(row.label), row.label, row.help, row.keywords ?? ""].join(" ").toLowerCase().includes(typed))
		.map((row) => ({
			value: { setting: row.key },
			label: __(row.label),
			description: __("Settings · {0}", [__(sections.get(row.section)!.label)]),
			icon: sections.get(row.section)!.icon.replace("lucide-", ""),
		}));
}
