// The child tables a parent's editor opens in its own page (`&table=<Table fieldname>`): one
// editor each, loaded once per page load, whose edits join the parent's undo stack and save.
import { computed, shallowRef, type InjectionKey } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { ChildEdits } from "./childEdits";
import type { ChildSave } from "./childSave";
import { pendingChild } from "./childSource";
import { DesignCanvas } from "./designCanvas";
import { loadEditor, type EditorState } from "./editorSource";
import type { PendingEdits } from "./pendingEdits";

export interface ChildSession {
	/** The parent's Table field it opened from. */
	table: string;
	state: EditorState;
	edits: ChildEdits;
	canvas: DesignCanvas;
}

export const CHILD_TABLES: InjectionKey<ChildTables> = Symbol("ChildTables");

export class ChildTables {
	/** The child editor the page shows; `null` shows the parent's. */
	readonly open = shallowRef<ChildSession | null>(null);
	/** The DocType whose Table field opened the child editor shown now. */
	readonly parentDoctype = computed(() => (this.open.value ? (this.parent()?.state.doctype ?? null) : null));
	private sessions = shallowRef(new Map<string, ChildSession>());
	private wanted: string | null = null;

	constructor(
		private edits: PendingEdits,
		private parent: () => DesignCanvas | null,
	) {}

	/** Opens the child of the parent's Table field `table`; `null`, or a field with no child yet, shows the parent. */
	async show(table: string | null) {
		this.wanted = table;
		const doctype = table ? this.childOf(table) : null;
		if (!table || !doctype) return void (this.open.value = null);
		const session = this.sessions.value.get(doctype) ?? (await this.load(doctype));
		if (this.wanted === table) this.open.value = { ...session, table };
	}

	/** The parent's Table field that holds `doctype`, for an undo that reopens its editor. */
	tableOf(doctype: string): string | null {
		const field = this.parent()?.working.value.fields.find((one) => one.fieldtype === "Table" && one.options === doctype);
		return field?.fieldname ?? null;
	}

	/** A child's fields as its open editor has them, else `null`. */
	fields(doctype: string): RawMetaField[] | null {
		return this.sessions.value.get(doctype)?.canvas.working.value.fields ?? null;
	}

	/** Every child table with staged edits; a new one, which the parent's edits add, has no base version. */
	saves(): ChildSave[] {
		const added = this.added();
		return this.edits.childDoctypes().flatMap((doctype) => {
			const edits = this.edits.stagedFor(doctype);
			if (added.includes(doctype)) return [{ doctype, edits }];
			const session = this.sessions.value.get(doctype);
			return session && !session.state.pending ? [{ doctype, edits, base_version: session.state.base_version }] : [];
		});
	}

	/** Drops every child editor, for a parent that loads again. */
	reset() {
		this.sessions.value = new Map();
		this.open.value = null;
	}

	private childOf(table: string): string | null {
		const field = this.parent()?.field(table);
		return field?.fieldtype === "Table" && field.options ? field.options : null;
	}

	private added(): string[] {
		return this.edits.staged.value
			.filter((edit) => edit.act === "fields.add_child_table")
			.map((edit) => String(edit.name));
	}

	private async load(doctype: string): Promise<ChildSession> {
		const parent = this.parent()!.state;
		const state = this.added().includes(doctype) ? pendingChild(doctype, parent) : await loadEditor(doctype, parent.mode);
		const edits = new ChildEdits(this.edits, state);
		const session = { table: "", state, edits, canvas: new DesignCanvas(state, edits) };
		this.sessions.value = new Map(this.sessions.value).set(doctype, session);
		return session;
	}
}
