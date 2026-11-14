// The child tables a parent's editor opens in its own page (`&table=<Table fieldname>`): one
// editor each, loaded once per page load, whose edits join the parent's undo stack and save.
import { computed, shallowRef, type InjectionKey } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { ChildEdits } from "./childEdits";
import type { ChildSave } from "./childSave";
import { pendingChild } from "./childSource";
import { DesignCanvas } from "./designCanvas";
import type { ForkWarning } from "./forkWarning";
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
	/** The latest `show`; an older one whose load lands after it opens nothing. */
	private wanted: object | null = null;
	/** Bumped by `reset`: a load that started for an earlier parent keeps nothing. */
	private generation = 0;

	constructor(
		private edits: PendingEdits,
		private parent: () => DesignCanvas | null,
		private forks: ForkWarning | null = null,
	) {}

	/** Opens the child of the parent's Table field `table`; `null`, or a field with no child yet, shows the parent. */
	async show(table: string | null) {
		const wanted = (this.wanted = {});
		const doctype = table ? this.childOf(table) : null;
		if (!table || !doctype) return void (this.open.value = null);
		const session = this.sessions.value.get(doctype) ?? (await this.load(doctype));
		if (this.wanted === wanted) this.open.value = { ...session, table };
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

	/** A loaded child editor's canvas, else `null`. */
	canvasOf(doctype: string): DesignCanvas | null {
		return this.sessions.value.get(doctype)?.canvas ?? null;
	}

	/** A child editor's canvas, loading the child when no editor has it yet. */
	async loaded(doctype: string): Promise<DesignCanvas> {
		return (this.sessions.value.get(doctype) ?? (await this.load(doctype))).canvas;
	}

	/** Every child table with staged edits; a new one, which the parent's edits add, has no base version. */
	saves(): ChildSave[] {
		const added = this.added();
		const named = this.named();
		return this.edits.childDoctypes().flatMap((doctype) => {
			const edits = this.edits.stagedFor(doctype);
			if (added.includes(doctype)) return named.has(doctype) ? [{ doctype, edits }] : [];
			const session = this.sessions.value.get(doctype);
			if (!session) throw new Error(`The child table ${doctype} has staged edits but no editor.`);
			return [{ doctype, edits, base_version: session.state.base_version }];
		});
	}

	/** A saved child's own call wrote its edits: they leave the stack, and its editor loads it again. */
	async saved(doctype: string) {
		this.edits.drop(doctype);
		const sessions = new Map(this.sessions.value);
		sessions.delete(doctype);
		this.sessions.value = sessions;
		const open = this.open.value;
		if (open?.state.doctype === doctype) await this.show(open.table);
	}

	/** A child's export wrote its app layout files after its editor loaded them: its next save compares to these. */
	rebaseAppLayouts(doctype: string, appLayouts: Record<string, string>) {
		const session = this.sessions.value.get(doctype);
		if (!session) return;
		const { base_version } = session.state;
		session.state = { ...session.state, base_version: { ...base_version, app_layouts: { ...base_version.app_layouts, ...appLayouts } } };
	}

	clearErrors() {
		for (const session of this.sessions.value.values()) session.canvas.errors.value = [];
	}

	/** Drops every child editor, for a parent that loads again. */
	reset() {
		this.generation++;
		this.wanted = null;
		this.sessions.value = new Map();
		this.open.value = null;
	}

	/** The child tables the parent's staged edits make. */
	added(): string[] {
		return this.edits.staged.value
			.filter((edit) => edit.act === "fields.add_child_table")
			.map((edit) => String(edit.name));
	}

	private childOf(table: string): string | null {
		const field = this.parent()?.field(table);
		return field?.fieldtype === "Table" && field.options ? field.options : null;
	}

	/** The child tables the parent's Table fields name now; a new child no field names is not saved. */
	private named(): Set<string> {
		const fields = this.parent()?.working.value.fields ?? [];
		return new Set(fields.filter((field) => field.fieldtype === "Table" && field.options).map((field) => field.options!));
	}

	private async load(doctype: string): Promise<ChildSession> {
		const parent = this.parent()!.state;
		const generation = this.generation;
		const state = this.added().includes(doctype) ? pendingChild(doctype, parent) : await loadEditor(doctype, parent.mode);
		const edits = new ChildEdits(this.edits, state);
		const session = { table: "", state, edits, canvas: new DesignCanvas(state, edits, this.forks) };
		if (generation === this.generation) this.sessions.value = new Map(this.sessions.value).set(doctype, session);
		return session;
	}
}
