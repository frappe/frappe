// vuedraggable reports a drop as `added`/`moved` to the list it lands in and `removed` to the one
// it left: only the first stages an act, or one drop would stage two.
import { acts } from "@/acts/dispatcher";
import type { LayoutTreeColumn, LayoutTreeSection, LayoutTreeTab } from "./layoutTree";
import type { DesignCanvas } from "./designCanvas";
import { addFieldType, type NewType } from "./newField";
import { removeField } from "./fieldPanel";

export interface DragChange<T> {
	added?: { element: T; newIndex: number };
	moved?: { element: T; newIndex: number };
	removed?: { element: T };
}

/** A field dropped in a column, or on a tab's name: the end of that tab's first section. */
export function dropField(
	canvas: DesignCanvas,
	change: DragChange<string | NewType>,
	into: { section: string; column: string } | { tab: string },
) {
	const landed = change.added ?? change.moved;
	// The bin covers the columns, so Sortable still reports a drop under it: that drop is the bin's.
	if (!landed || canvas.drag.value.overBin) return;
	const index = "tab" in into ? {} : { index: landed.newIndex };
	if (typeof landed.element !== "string") return void addFieldType(canvas, landed.element.type, { ...into, ...index });
	const fieldname = landed.element;
	const act = canvas.place(fieldname) ? "canvas.move_field" : "canvas.place_field";
	void acts.perform(act, { fieldname, ...into, ...index });
}

/** Starts a placed field's drag: the bin shows, and it knows which field the item is. */
export function startDrag(canvas: DesignCanvas, item: HTMLElement) {
	canvas.drag.value = { active: true, overBin: false, fieldname: item.dataset.canvasField };
}

/** Ends a placed field's drag: released over the bin, the field leaves as the panel's trash would. */
export function dropOnBin(canvas: DesignCanvas) {
	const { overBin, fieldname } = canvas.drag.value;
	canvas.drag.value = { active: false, overBin: false };
	const field = fieldname ? canvas.field(fieldname) : undefined;
	if (!overBin || !field) return;
	// A hidden field stays hidden: the panel trash would show it again, the bin has no such verb.
	if (canvas.customize?.hidesOnRemove(field.fieldname) && field.hidden) return;
	void removeField(canvas, field);
}

export function dropOffLayout(canvas: DesignCanvas, change: DragChange<string>) {
	// Over the bin, the drop is the bin's too: a canceled removal must leave the layout as it was.
	if (canvas.drag.value.overBin) return;
	if (typeof change.added?.element === "string") void acts.perform("canvas.unplace_field", { fieldname: change.added.element });
}

export function dropSection(change: DragChange<LayoutTreeSection>, tab: string) {
	const landed = change.added ?? change.moved;
	if (landed) void acts.perform("canvas.move_section", { section: landed.element.name, tab, index: landed.newIndex });
}

export function dropColumn(canvas: DesignCanvas, change: DragChange<LayoutTreeColumn>, toSection: string) {
	const landed = change.added ?? change.moved;
	if (!landed) return;
	const sections = canvas.tabs.value.flatMap((tab) => tab.sections);
	const from = sections.find((section) => section.columns.includes(landed.element));
	void acts.perform("canvas.move_column", {
		section: from?.name,
		column: landed.element.name,
		to_section: toSection,
		index: landed.newIndex,
	});
}

export function dropTab(change: DragChange<LayoutTreeTab>) {
	if (change.moved) void acts.perform("canvas.move_tab", { tab: change.moved.element.name, index: change.moved.newIndex });
}

/** What every canvas list passes to vuedraggable; a click on a button or an input never starts a drag. */
export const DRAG_OPTIONS = {
	forceFallback: true,
	fallbackOnBody: false,
	animation: 120,
	filter: "button, input",
	preventOnFilter: false,
};
