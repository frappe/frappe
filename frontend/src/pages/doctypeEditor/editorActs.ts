// The DocType editor's act surfaces. Every act is `<surface>.<item>` and takes one value; later
// slices add `layouts`, `canvas`, `fields`, `settings`, `danger` and `customize` here.
import { toast } from "frappe-ui";
import { onScopeDispose, type Ref } from "vue";
import { acts, type ActEntry, type ActItem, type ActOption } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import type { EditorTab, PendingEdits } from "./pendingEdits";

export interface EditorActsHost {
	edits: PendingEdits;
	tab: Ref<EditorTab>;
	find: () => void;
	/** The record Preview draws, by name; `null` draws an empty form. */
	previewRecord: (name: string | null) => void;
	recordOptions: (query: string) => Promise<ActOption[]>;
}

const TABS: { value: EditorTab; label: string }[] = [
	{ value: "editor", label: "Editor" },
	{ value: "settings", label: "Settings" },
	{ value: "preview", label: "Preview" },
];

/** Registers the editor's surfaces for the page's life. */
export function useEditorActs(host: EditorActsHost) {
	const release = acts.register({
		surfaces: { editor: () => editorItems(host).map((item) => ({ item, hidden: false }) as ActEntry) },
		context: () => host,
		passes: () => true,
		settled: () => undefined,
		hold: async (work) => work(),
		failed: (error) => void toast.error(errorMessage(error)),
	});
	onScopeDispose(release);
}

export function editorItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return [
		{
			name: "undo",
			label: __("Undo"),
			icon: "corner-up-left",
			key: "Mod+Z",
			when: () => host.edits.canUndo.value,
			run: () => host.edits.undo(),
		},
		{
			name: "redo",
			label: __("Redo"),
			icon: "corner-up-right",
			key: "Mod+Shift+Z",
			when: () => host.edits.canRedo.value,
			run: () => host.edits.redo(),
		},
		{
			name: "open_tab",
			label: __("Open tab"),
			argument: {
				label: __("Tab"),
				options: () => TABS.map((tab) => ({ value: tab.value, label: __(tab.label) })),
			},
			run: (_context, tab: EditorTab) => (host.tab.value = tab),
		},
		{ name: "find", label: __("Find a field"), icon: "search", key: "Mod+J", run: () => host.find() },
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
