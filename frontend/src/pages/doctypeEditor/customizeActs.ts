// Customize mode's header acts: the Design | Customize switch, and the ⋯ menu's Reset all
// customizations and Export customizations. Both write at once, outside the pending edits.
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { ActItem } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import type { EditorActsHost } from "./editorActs";
import type { EditorState } from "./editorSource";
import type { EditorMode } from "./pendingEdits";

export const RESET_METHOD = "frappe.desk.doctype_editor.customize_acts.reset_all";
export const EXPORT_METHOD = "frappe.desk.doctype_editor.customize_acts.export";

export interface CustomizationCounts {
	custom_fields: number;
	property_setters: number;
	layouts: number;
}

/** What a reset deletes, and the rows apps made that it keeps. */
export interface ResetCounts {
	delete: CustomizationCounts;
	keep: CustomizationCounts;
}

export interface ExportAnswers {
	module: string;
	sync_on_migrate: boolean;
	with_permissions: boolean;
}

export interface CustomizeHost {
	developerMode: boolean;
	/** Opens the other mode; the route guard asks about pending edits first. */
	setMode: (mode: EditorMode) => void;
	/** The open canvas's DocType, which may be a child table: the one the act writes. */
	askReset: (state: EditorState, counts: ResetCounts) => Promise<true | null>;
	askExport: (state: EditorState) => Promise<ExportAnswers | null>;
	/** Loads the DocType again, dropping pending edits. */
	reload: () => Promise<unknown>;
}

/** `editor.set_mode`, offered when the reader may open both modes. */
export function modeItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const state = () => host.canvas()?.state;
	return [
		{
			name: "set_mode",
			label: __("Switch mode"),
			icon: "repeat",
			argument: {
				label: __("Mode"),
				options: () => (state()?.modes ?? []).map((mode) => ({ value: mode, label: __(mode) })),
			},
			when: () => (state()?.modes.length ?? 0) > 1,
			run: (_context, mode: EditorMode) => {
				if (mode !== state()?.mode) host.customize.setMode(mode);
			},
		},
	];
}

/** The `customize` surface: the ⋯ menu's acts in Customize mode. */
export function customizeItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const customizing = () => Boolean(host.canvas()?.customize);
	return [
		{
			name: "reset_all",
			label: __("Reset all customizations"),
			icon: "rotate-ccw",
			when: customizing,
			run: () => resetAll(host),
		},
		{
			name: "export",
			label: __("Export customizations"),
			icon: "package",
			when: () => customizing() && host.customize.developerMode,
			run: () => exportCustomizations(host),
		},
	];
}

/** The lines Reset all's dialog lists, one per kind of row it deletes. */
export function resetLines(counts: CustomizationCounts): string[] {
	const { custom_fields: fields, property_setters: setters, layouts } = counts;
	return [
		fields && __n("{0} custom field", "{0} custom fields", fields, [fields]),
		setters && __n("{0} property change", "{0} property changes", setters, [setters]),
		layouts && __n("{0} site layout", "{0} site layouts", layouts, [layouts]),
	].filter((line): line is string => Boolean(line));
}

async function resetAll(host: EditorActsHost) {
	const state = host.canvas()!.state;
	const { doctype } = state;
	const { data: counts } = await runMethod<ResetCounts>(RESET_METHOD, { doctype });
	if (!(await host.customize.askReset(state, counts))) return;
	await runMethod(RESET_METHOD, { doctype, confirm: 1 });
	toast.success(__("Reset {0}.", [doctype]));
	await host.customize.reload();
}

async function exportCustomizations(host: EditorActsHost) {
	const state = host.canvas()!.state;
	const { doctype } = state;
	const answers = await host.customize.askExport(state);
	if (!answers) return;
	const { data: path } = await runMethod<string | null>(EXPORT_METHOD, { doctype, ...answers });
	toast.success(path ? __("Exported to {0}.", [path]) : __("{0} has no customizations to export.", [doctype]));
}
