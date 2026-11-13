// The one-step moves Alt+Arrow and the canvas menus make, as the keys of a canvas move act.
// `null` when the item already sits at that edge.
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";
import type { CanvasSelection } from "./designCanvas";

export type Direction = "up" | "down" | "left" | "right";

export interface CanvasMove {
	act: "canvas.move_field" | "canvas.move_section" | "canvas.move_column" | "canvas.move_tab";
	value: Record<string, unknown>;
}

export function canvasMove(tabs: LayoutTree, selection: CanvasSelection, direction: Direction): CanvasMove | null {
	const value = MOVES[selection.kind](tabs, selection as never, direction);
	return value && { act: `canvas.move_${selection.kind}`, value };
}

const MOVES: Record<CanvasSelection["kind"], (tabs: LayoutTree, selection: never, direction: Direction) => Record<string, unknown> | null> = {
	field: fieldMove,
	section: sectionMove,
	column: columnMove,
	tab: tabMove,
};

/** Up and down within the column, then across the tab's sections; left and right to the next column. */
function fieldMove(tabs: LayoutTree, { fieldname }: { fieldname: string }, direction: Direction) {
	for (const tab of tabs) {
		const columns = tab.sections.flatMap((section) =>
			section.columns.map((column) => ({ section: section.name!, column })),
		);
		const at = columns.findIndex(({ column }) => column.fields.includes(fieldname));
		if (at === -1) continue;
		const { section, column } = columns[at];
		const index = column.fields.indexOf(fieldname);
		const across = (to: (typeof columns)[number] | undefined, toIndex?: number) =>
			to ? { fieldname, section: to.section, column: to.column.name, index: toIndex } : null;
		if (direction === "up" && index > 0) return { fieldname, section, column: column.name, index: index - 1 };
		if (direction === "down" && index < column.fields.length - 1) {
			return { fieldname, section, column: column.name, index: index + 1 };
		}
		if (direction === "up") return across(columns[at - 1]);
		if (direction === "down") return across(columns[at + 1], 0);
		const step = direction === "left" ? -1 : 1;
		const next = columns[at + step];
		return next?.section === section ? across(next, Math.min(index, next.column.fields.length)) : null;
	}
	return null;
}

/** Up and down within the tab; left and right to the end of the tab beside it. */
function sectionMove(tabs: LayoutTree, { section }: { section: string }, direction: Direction) {
	const at = tabs.findIndex((tab) => tab.sections.some((one) => one.name === section));
	if (at === -1) return null;
	const sections = tabs[at].sections;
	const index = sections.findIndex((one) => one.name === section);
	if (direction === "up" || direction === "down") {
		const to = index + (direction === "up" ? -1 : 1);
		return to < 0 || to >= sections.length ? null : { section, tab: tabs[at].name, index: to };
	}
	const tab = tabs[at + (direction === "left" ? -1 : 1)];
	return tab ? { section, tab: tab.name, index: tab.sections.length } : null;
}

function columnMove(tabs: LayoutTree, { section, column }: { section: string; column: string }, direction: Direction) {
	if (direction === "up" || direction === "down") return null;
	const columns = tabs.flatMap((tab) => tab.sections).find((one) => one.name === section)?.columns ?? [];
	const to = columns.findIndex((one) => one.name === column) + (direction === "left" ? -1 : 1);
	return to < 0 || to >= columns.length ? null : { section, column, to_section: section, index: to };
}

function tabMove(tabs: LayoutTree, { tab }: { tab: string }, direction: Direction) {
	if (direction === "up" || direction === "down") return null;
	const to = tabs.findIndex((one) => one.name === tab) + (direction === "left" ? -1 : 1);
	return to < 0 || to >= tabs.length ? null : { tab, index: to };
}
