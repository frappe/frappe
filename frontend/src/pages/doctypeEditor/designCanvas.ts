// The Design canvas: the working state the staged edits make, what is selected, and which tab is open.
import { computed, ref, shallowRef } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import {
	DETAILS,
	editorBase,
	fieldsOffLayout,
	savedName,
	workingState,
	type FlatEdit,
	type WorkingState,
} from "./editorModel";
import { CustomizeView } from "./customizeView";
import type { EditorState } from "./editorSource";
import { LayoutTreeEditor } from "./layoutTree";
import type { EditStage } from "./pendingEdits";
import { findLayout, layoutOf, type LayoutRef } from "./workingLayouts";

export type CanvasSelection =
	| { kind: "field"; fieldname: string }
	| { kind: "section"; section: string }
	| { kind: "column"; section: string; column: string }
	| { kind: "tab"; tab: string };

/** A save's refusal, at what the editor shows it on. */
export interface SaveError {
	target: {
		kind: "field" | "container" | "layout" | "setting" | "banner";
		fieldname?: string;
		property?: string;
		layout?: string;
		container?: string;
	};
	message: string;
	/** The index of the staged edit it refuses. */
	edit?: number;
	code?: string;
	/** The child table it refuses, in a call that saves more than one DocType. */
	doctype?: string;
}

/** Where a field sits on the layout. */
export interface FieldPlace {
	tab: string;
	section: string;
	column: string;
	index: number;
}

export class DesignCanvas {
	readonly base: WorkingState;
	readonly working = computed(() => workingState(this.base, this.edits.staged.value));
	/** The layout the canvas draws and every canvas edit names; a gone one falls back to its type's default. */
	readonly openLayout = computed<LayoutRef>(() => this.existing(this.wanted.value));
	readonly layout = computed(() => layoutOf(this.working.value, this.openLayout.value));
	readonly tabs = computed(() => this.layout.value?.tabs ?? []);
	readonly selection = shallowRef<CanvasSelection | null>(null);
	/** The open tab's name; the first tab when it names none that exists. */
	readonly openTabName = ref("");
	readonly openTab = computed(
		() => this.tabs.value.find((tab) => tab.name === this.openTabName.value) ?? this.tabs.value[0],
	);
	/** The fieldnames the last save's mandatory error asked for. */
	readonly askedOnSave = shallowRef<string[]>([]);
	readonly offLayout = computed(() =>
		fieldsOffLayout(this.working.value, this.askedOnSave.value, this.openLayout.value),
	);
	readonly trayOpen = ref(true);
	/** The last save's errors; each draws at its field or container. */
	readonly errors = shallowRef<SaveError[]>([]);
	/** The section whose "Add field" input is open. */
	readonly adding = shallowRef<string | null>(null);
	readonly selectedField = computed<RawMetaField | null>(() => {
		const selected = this.selection.value;
		if (selected?.kind !== "field") return null;
		return this.field(selected.fieldname) ?? null;
	});
	readonly editable: boolean;
	/** `null` in Design. */
	readonly customize: CustomizeView | null;
	private wanted = shallowRef<LayoutRef>(DETAILS);

	constructor(
		readonly state: EditorState,
		private edits: EditStage,
	) {
		this.base = editorBase(state);
		this.editable = state.modes.includes(state.mode);
		this.customize =
			state.mode === "Customize" ? new CustomizeView(state, this.base, this.working, () => this.edits.staged.value) : null;
	}

	/** Stages the edits as one undo step; throws `EditRefused`, and stages nothing, when the replay refuses one. */
	stage(...edits: FlatEdit[]) {
		workingState(this.base, [...this.edits.staged.value, ...edits]);
		this.edits.stage(...edits.map(({ act, ...value }) => ({ act, value, tab: "editor" as const })));
	}

	/** As `stage`, for the Settings tab: undo opens it. Customize sets settings while its canvas is read-only. */
	stageSettings(...edits: FlatEdit[]) {
		workingState(this.base, [...this.edits.staged.value, ...edits]);
		this.edits.stage(...edits.map(({ act, ...value }) => ({ act, value, tab: "settings" as const })));
	}

	/** Draws another layout, from its first tab, with nothing selected. */
	open(layout: LayoutRef) {
		this.wanted.value = layout;
		this.selection.value = null;
		this.openTabName.value = "";
		this.adding.value = null;
	}

	select(selection: CanvasSelection | null) {
		this.selection.value = selection;
		const tab = selection && this.tabOf(selection);
		if (tab) this.openTabName.value = tab;
	}

	field(fieldname: string): RawMetaField | undefined {
		return this.working.value.fields.find((field) => field.fieldname === fieldname);
	}

	/** The fieldname the database has; `null` for a field added since the save. */
	savedName(fieldname: string): string | null {
		return savedName(this.working.value, fieldname);
	}

	/** The field as the editor loaded it; `undefined` for one added since. */
	savedField(fieldname: string): RawMetaField | undefined {
		const saved = this.savedName(fieldname);
		return this.base.fields.find((field) => field.fieldname === saved);
	}

	/** How many records hold a value in the field's column. */
	valueCount(fieldname: string): number {
		const saved = this.savedName(fieldname);
		return saved ? (this.state.value_counts[saved] ?? 0) : 0;
	}

	errorsAt(kind: "field" | "container" | "setting", name: string): string[] {
		return this.errors.value
			.filter(({ target }) => target.kind === kind && (target.fieldname ?? target.container ?? target.property) === name)
			.map((error) => error.message);
	}

	place(fieldname: string): FieldPlace | null {
		for (const tab of this.tabs.value) {
			for (const section of tab.sections) {
				for (const column of section.columns) {
					const index = column.fields.indexOf(fieldname);
					if (index !== -1) {
						return { tab: tab.name!, section: section.name!, column: column.name!, index };
					}
				}
			}
		}
		return null;
	}

	/** The section `A` and "Add field" add to: the selection's, else the open tab's last. */
	targetSection(): string | null {
		const selected = this.selection.value;
		if (selected?.kind === "field") {
			const place = this.place(selected.fieldname);
			if (place) return place.section;
		}
		if (selected?.kind === "section" || selected?.kind === "column") return selected.section;
		return this.openTab.value?.sections.at(-1)?.name ?? null;
	}

	/** Where a field added to `section` goes: after the selected field there, else at the end of its shortest column. */
	addPlace(section: string): { section: string; column: string; index?: number } {
		const selected = this.selection.value;
		const place = selected?.kind === "field" ? this.place(selected.fieldname) : null;
		if (place?.section === section) return { section, column: place.column, index: place.index + 1 };
		const columns = new LayoutTreeEditor(this.tabs.value).section(section).columns;
		const shortest = columns.reduce((one, other) => (other.fields.length < one.fields.length ? other : one));
		return { section, column: shortest.name! };
	}

	private existing(layout: LayoutRef): LayoutRef {
		const { layouts } = this.working.value;
		if (!layouts[layout.type]) return DETAILS;
		if (layout.id && !findLayout(this.working.value, layout)) return { type: layout.type };
		return layout;
	}

	private tabOf(selection: CanvasSelection): string | undefined {
		if (selection.kind === "tab") return selection.tab;
		if (selection.kind === "field") return this.place(selection.fieldname)?.tab;
		return this.tabs.value.find((tab) => tab.sections.some((one) => one.name === selection.section))?.name;
	}
}
