// A DocType editor without its page: the acts, the canvas and the save, on a small "Task Note".
import { effectScope, ref } from "vue";
import { DesignCanvas } from "../designCanvas";
import { useEditorActs, type EditorActsHost } from "../editorActs";
import { EditorSave } from "../editorSave";
import type { EditorState } from "../editorSource";
import { PendingEdits, type BaseVersion, type EditorTab } from "../pendingEdits";

export const VERSION: BaseVersion = { doctype: "2026-11-13 10:00:00", layouts: {}, app_layouts: {} };

export function taskNote(overrides: Partial<EditorState> = {}): EditorState {
	return {
		doctype: "Task Note",
		mode: "Design",
		modes: ["Design"],
		base_version: VERSION,
		custom: 1,
		module: "Desk",
		app_title: null,
		record_count: 4,
		value_counts: { subject: 4, notes: 2 },
		layouts: {
			Details: [
				{
					name: null,
					source: "fallback",
					omitted: [],
					layout: [
						{
							name: "details",
							sections: [
								{ name: "main", columns: [{ name: "column_1", fields: ["subject", "status"] }] },
								{ name: "more", dependsOn: "eval:doc.status", columns: [{ name: "column_1", fields: ["notes"] }] },
							],
						},
					],
				},
			],
		},
		definition: {
			name: "Task Note",
			fields: [
				{ fieldname: "subject", label: "Subject", fieldtype: "Small Text" },
				{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nDone" },
				{ fieldname: "notes", label: "Notes", fieldtype: "Text", reqd: 1 },
				{ fieldname: "spare", label: "Spare", fieldtype: "Data", reqd: 1 },
			],
		},
		...overrides,
	} as EditorState;
}

/** Mounts the acts on `initial`; a reload opens `reloaded()` (default: `initial` again) with no edits. */
export function mountEditor(
	initial: EditorState,
	options: { reloaded?: () => EditorState; openList?: () => void } = {},
) {
	const tab = ref<EditorTab>("editor");
	const head = { doctype: initial.doctype, mode: initial.mode, base_version: initial.base_version };
	const edits = new PendingEdits(head, (opened) => (tab.value = opened));
	let canvas = new DesignCanvas(initial, edits);
	const open = (state: EditorState) => {
		Object.assign(head, { doctype: state.doctype, mode: state.mode, base_version: state.base_version });
		edits.clear();
		canvas = new DesignCanvas(state, edits);
		return canvas;
	};
	const next = () => options.reloaded?.() ?? initial;
	const created: string[] = [];
	const save = new EditorSave({
		edits,
		canvas: () => canvas,
		reload: async () => open(next()),
		created: async (doctype) => {
			created.push(doctype);
			return open({ ...next(), doctype, pending: undefined });
		},
	});
	const host: EditorActsHost = {
		edits,
		tab,
		canvas: () => canvas,
		find: () => undefined,
		previewRecord: () => undefined,
		recordOptions: async () => [],
		save,
		openList: options.openList ?? (() => undefined),
	};
	const scope = effectScope();
	scope.run(() => useEditorActs(host));
	return {
		get canvas() {
			return canvas;
		},
		edits,
		head,
		save,
		created,
		stop: () => scope.stop(),
	};
}
