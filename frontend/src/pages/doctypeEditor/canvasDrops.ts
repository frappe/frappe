// vuedraggable reports a drop as `added`/`moved` to the list it lands in and `removed` to the one
// it left: only the first stages an act, or one drop would stage two.
import { acts } from "@/acts/dispatcher";
import type { LayoutTreeColumn, LayoutTreeSection, LayoutTreeTab } from "./layoutTree";
import type { DesignCanvas } from "./designCanvas";

export interface DragChange<T> {
	added?: { element: T; newIndex: number };
	moved?: { element: T; newIndex: number };
	removed?: { element: T };
}

/** A field dropped in a column, or on a tab's name: the end of that tab's first section. */
export function dropField(
	canvas: DesignCanvas,
	change: DragChange<string>,
	into: { section: string; column: string } | { tab: string },
) {
	const landed = change.added ?? change.moved;
	if (!landed) return;
	const fieldname = landed.element;
	const act = canvas.place(fieldname) ? "canvas.move_field" : "canvas.place_field";
	const index = "tab" in into ? {} : { index: landed.newIndex };
	void acts.perform(act, { fieldname, ...into, ...index });
}

export function dropOffLayout(change: DragChange<string>) {
	if (change.added) void acts.perform("canvas.unplace_field", { fieldname: change.added.element });
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
