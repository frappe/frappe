// A child table's share of the page's pending edits: what its canvas replays, and the edits it
// stages, tagged with the child so they join the parent's undo stack and save.
import { computed } from "vue";
import { DETAILS } from "./designCanvas";
import { editorBase, EditRefused, workingState, type FlatEdit, type WorkingState } from "./editorModel";
import type { EditorState } from "./editorSource";
import { LAYOUT_BREAKS } from "./fieldRules";
import type { Edit, EditStage, PendingEdits } from "./pendingEdits";

const PLACE_KEYS = ["layout", "section", "column", "index", "tab"];

export class ChildEdits implements EditStage {
	readonly doctype: string;
	private pending: boolean;
	private base: WorkingState;
	/** A new child has no layout until its first save, so its canvas draws its fields in order. */
	readonly staged = computed<FlatEdit[]>(() => {
		const own = this.edits.stagedFor(this.doctype);
		return this.pending ? [...own, ...this.drawnInOrder(own)] : own;
	});

	constructor(
		private edits: PendingEdits,
		state: EditorState,
	) {
		this.doctype = state.doctype;
		this.pending = Boolean(state.pending);
		this.base = editorBase(state);
	}

	stage(...edits: Edit[]) {
		const own = edits.map((edit) => ({ ...edit, value: this.saved(edit), doctype: this.doctype }));
		this.edits.stage(...own);
	}

	/** A DocType setting: the last staged value, else the loaded one. */
	setting(state: EditorState, property: "editable_grid" | "allow_bulk_edit"): boolean {
		const set = this.edits
			.stagedFor(this.doctype)
			.filter((edit) => edit.act === "settings.set_doctype_property" && edit.property === property)
			.at(-1);
		return Boolean(set ? set.value : state.definition[property]);
	}

	/** The server refuses a layout for a child table it has not inserted yet, so a new child's edits carry none. */
	private saved(edit: Edit): Record<string, unknown> {
		if (!this.pending) return edit.value;
		if (edit.act.startsWith("canvas.")) {
			throw new EditRefused("Save the new child table {0} before you lay it out.", [this.doctype]);
		}
		return Object.fromEntries(Object.entries(edit.value).filter(([key]) => !PLACE_KEYS.includes(key)));
	}

	private drawnInOrder(own: FlatEdit[]): FlatEdit[] {
		return workingState(this.base, own)
			.fields.filter((field) => !LAYOUT_BREAKS.includes(field.fieldtype))
			.map((field) => ({ act: "canvas.place_field", layout: DETAILS, fieldname: field.fieldname, section: "main", column: "column" }));
	}
}
