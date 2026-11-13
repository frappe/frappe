import { computed, ref, shallowRef } from "vue";
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
	/** The child table it edits; absent for the DocType the page opened. */
	doctype?: string;
}

/** What a canvas replays and stages into. */
export interface EditStage {
	readonly staged: { readonly value: FlatEdit[] };
	stage(...edits: Edit[]): void;
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

	/** While a save runs, nothing stages, undoes or redoes: the save's reload drops every edit. */
	readonly locked = ref(false);

	readonly dirty = computed(() => this.done.value.length > 0);
	readonly canUndo = computed(() => this.dirty.value && !this.locked.value);
	readonly canRedo = computed(() => this.undone.value.length > 0 && !this.locked.value);
	/** The page DocType's staged edits in order, as the save sends them; a save error's `edit` indexes this list. */
	readonly staged = computed<FlatEdit[]>(() => this.stagedFor(undefined));

	constructor(
		private head: Omit<PendingEditsPayload, "edits">,
		private openTab: (tab: EditorTab, doctype?: string) => void,
	) {}

	/** One DocType's staged edits in order; `undefined` names the page's own DocType. */
	stagedFor(doctype: string | undefined): FlatEdit[] {
		return this.done.value
			.flat()
			.filter((edit) => edit.doctype === doctype)
			.map((edit) => ({ ...edit.value, act: edit.act }));
	}

	/** The child tables with staged edits. */
	childDoctypes(): string[] {
		const doctypes = this.done.value.flat().map((edit) => edit.doctype);
		return [...new Set(doctypes.filter((doctype): doctype is string => Boolean(doctype)))];
	}

	/** Stage one change; several edits given together undo as one step. */
	stage(...edits: Edit[]) {
		if (!edits.length || this.locked.value) return;
		this.done.value = [...this.done.value, edits];
		this.undone.value = [];
	}

	/** Undo the last staged change, from either tab, and open the tab it changed. */
	undo() {
		const step = this.done.value.at(-1);
		if (!step || this.locked.value) return;
		this.done.value = this.done.value.slice(0, -1);
		this.undone.value = [...this.undone.value, step];
		this.reopen(step);
	}

	redo() {
		const step = this.undone.value.at(-1);
		if (!step || this.locked.value) return;
		this.undone.value = this.undone.value.slice(0, -1);
		this.done.value = [...this.done.value, step];
		this.reopen(step);
	}

	/** The undo steps in order, for a reload that applies them again. */
	get steps(): readonly Edit[][] {
		return this.done.value;
	}

	/** The version a later save compares against, after a save or a file write moved it. */
	rebase(version: BaseVersion) {
		this.head.base_version = version;
	}

	/** Drop one child table's steps, once its own save call wrote them. */
	drop(doctype: string) {
		const others = (steps: Edit[][]) => steps.filter((step) => step[0].doctype !== doctype);
		this.done.value = others(this.done.value);
		this.undone.value = others(this.undone.value);
	}

	/** Drop every edit, for a page that opens another DocType or mode. */
	clear() {
		this.done.value = [];
		this.undone.value = [];
	}

	payload(): PendingEditsPayload {
		return { ...this.head, edits: this.staged.value };
	}

	private reopen(step: Edit[]) {
		const last = step.at(-1)!;
		this.openTab(last.tab, last.doctype);
	}
}
