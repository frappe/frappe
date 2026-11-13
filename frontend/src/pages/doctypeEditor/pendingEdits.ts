import { computed, shallowRef } from "vue";

export type EditorTab = "editor" | "settings" | "preview";
export type EditorMode = "design" | "customize";

/** One staged edit act: its `<surface>.<item>` name, its one value, and the tab it changed. */
export interface Edit {
	act: string;
	value: unknown;
	tab: Exclude<EditorTab, "preview">;
}

export interface PendingEditsPayload {
	doctype: string;
	mode: EditorMode;
	base_version: string;
	edits: Edit[];
}

/** The edits a save sends, with one undo and redo stack shared by the Editor and Settings tabs. */
export class PendingEdits {
	private done = shallowRef<Edit[]>([]);
	private undone = shallowRef<Edit[]>([]);

	readonly canUndo = computed(() => this.done.value.length > 0);
	readonly canRedo = computed(() => this.undone.value.length > 0);
	readonly dirty = this.canUndo;

	constructor(
		private head: Omit<PendingEditsPayload, "edits">,
		private openTab: (tab: EditorTab) => void,
	) {}

	stage(edit: Edit) {
		this.done.value = [...this.done.value, edit];
		this.undone.value = [];
	}

	/** Undo the last staged edit, from either tab, and open the tab it changed. */
	undo() {
		const edit = this.done.value.at(-1);
		if (!edit) return;
		this.done.value = this.done.value.slice(0, -1);
		this.undone.value = [...this.undone.value, edit];
		this.openTab(edit.tab);
	}

	redo() {
		const edit = this.undone.value.at(-1);
		if (!edit) return;
		this.undone.value = this.undone.value.slice(0, -1);
		this.done.value = [...this.done.value, edit];
		this.openTab(edit.tab);
	}

	payload(): PendingEditsPayload {
		return { ...this.head, edits: this.done.value };
	}
}
