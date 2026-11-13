import { computed, shallowRef } from "vue";
import type { FlatEdit } from "./editorModel";

export type EditorTab = "editor" | "settings" | "preview";
/** The server's mode names; the address spells Customize `?mode=customize`. */
export type EditorMode = "Design" | "Customize";

/** What the editor loaded, as `versions.base_version` returns it; a save compares it to refuse stale edits. */
export interface BaseVersion {
	doctype: string;
	layouts: Record<string, string>;
	app_layouts: Record<string, string>;
}

/** One staged edit act: its `<surface>.<item>` name, its keys, and the tab it changed. */
export interface Edit {
	act: string;
	value: Record<string, unknown>;
	tab: Exclude<EditorTab, "preview">;
}

export interface PendingEditsPayload {
	doctype: string;
	mode: EditorMode;
	base_version: BaseVersion;
	edits: FlatEdit[];
}

/** The edits a save sends, with one undo and redo stack shared by the Editor and Settings tabs. */
export class PendingEdits {
	/** Each undo step: the edits one change staged together. */
	private done = shallowRef<Edit[][]>([]);
	private undone = shallowRef<Edit[][]>([]);

	readonly canUndo = computed(() => this.done.value.length > 0);
	readonly canRedo = computed(() => this.undone.value.length > 0);
	readonly dirty = this.canUndo;
	/** Every staged edit in order, as the save sends it; a save error's `edit` indexes this list. */
	readonly staged = computed<FlatEdit[]>(() =>
		this.done.value.flat().map((edit) => ({ ...edit.value, act: edit.act })),
	);

	constructor(
		private head: Omit<PendingEditsPayload, "edits">,
		private openTab: (tab: EditorTab) => void,
	) {}

	/** Stage one change; several edits given together undo as one step. */
	stage(...edits: Edit[]) {
		if (!edits.length) return;
		this.done.value = [...this.done.value, edits];
		this.undone.value = [];
	}

	/** Undo the last staged change, from either tab, and open the tab it changed. */
	undo() {
		const step = this.done.value.at(-1);
		if (!step) return;
		this.done.value = this.done.value.slice(0, -1);
		this.undone.value = [...this.undone.value, step];
		this.openTab(step.at(-1)!.tab);
	}

	redo() {
		const step = this.undone.value.at(-1);
		if (!step) return;
		this.undone.value = this.undone.value.slice(0, -1);
		this.done.value = [...this.done.value, step];
		this.openTab(step.at(-1)!.tab);
	}

	/** Drop every edit, for a page that opens another DocType or mode. */
	clear() {
		this.done.value = [];
		this.undone.value = [];
	}

	payload(): PendingEditsPayload {
		return { ...this.head, edits: this.staged.value };
	}
}
