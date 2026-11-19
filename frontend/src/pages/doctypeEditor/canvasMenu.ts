// The menus of the canvas, a section's "⋯" and the right-click on a section, column or field: the
// moves Alt+Arrow makes, then the item's own acts. And the click that selects one.
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { canvasMove, type Direction } from "./canvasMoves";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";
import { moveToTab, removeAction, removeField } from "./fieldPanel";

/** A read-only canvas may be a view beside the editor's own, so it selects on itself. */
export function selectOn(canvas: DesignCanvas, selection: CanvasSelection) {
	if (!canvas.editable) return canvas.select(selection);
	void acts.perform("canvas.select", selection);
}

export interface CanvasMenuOption {
	label: string;
	icon?: string;
	disabled?: boolean;
	onClick?: () => void;
	submenu?: CanvasMenuOption[];
}

/** What a menu opens on: a section's "⋯", or the right-click on a section, column or field. */
export type MenuItem = Exclude<CanvasSelection, { kind: "tab" }>;

/** A read-only canvas has no acts to offer, so no menu. */
export function canvasMenu(canvas: DesignCanvas, item: MenuItem): CanvasMenuOption[] {
	if (!canvas.editable) return [];
	if (item.kind === "field") return fieldMenu(canvas, item.fieldname);
	const moves = movesOf(canvas, item, item.kind === "section" ? SECTION_MOVES : COLUMN_MOVES);
	return [...moves, ...(item.kind === "section" ? sectionActs(item.section) : columnActs(canvas, item))];
}

type Names = [Direction, () => string, string][];

/** Labels are read when the menu opens: `__()` at module load runs before the translations arrive. */
const SECTION_MOVES: Names = [
	["up", () => __("Move up"), "lucide-arrow-up"],
	["down", () => __("Move down"), "lucide-arrow-down"],
	["left", () => __("Move to the tab before"), "lucide-arrow-left"],
	["right", () => __("Move to the tab after"), "lucide-arrow-right"],
];
const COLUMN_MOVES: Names = [
	["left", () => __("Move left"), "lucide-arrow-left"],
	["right", () => __("Move right"), "lucide-arrow-right"],
];
const FIELD_MOVES: Names = [
	SECTION_MOVES[0],
	SECTION_MOVES[1],
	["left", () => __("Move to the column before"), "lucide-arrow-left"],
	["right", () => __("Move to the column after"), "lucide-arrow-right"],
];

function movesOf(canvas: DesignCanvas, item: MenuItem, names: Names): CanvasMenuOption[] {
	return names.map(([direction, name, icon]) => {
		const move = canvasMove(canvas.tabs.value, item, direction);
		return { label: name(), icon, disabled: !move, onClick: () => move && acts.perform(move.act, move.value) };
	});
}

function sectionActs(section: string): CanvasMenuOption[] {
	const run = (act: string, value: unknown) => () => void acts.perform(act, value);
	return [
		{ label: __("Add column"), icon: "lucide-columns-2", onClick: run("canvas.add_column", { section }) },
		{ label: __("Remove section"), icon: "lucide-trash-2", onClick: run("canvas.remove_section", { section }) },
	];
}

/** The panel's Remove column: only a section of two or more columns loses one. */
function columnActs(canvas: DesignCanvas, { section, column }: { section: string; column: string }): CanvasMenuOption[] {
	const columns = canvas.tabs.value.flatMap((tab) => tab.sections).find((one) => one.name === section)?.columns;
	if ((columns?.length ?? 0) < 2) return [];
	const remove = async () => {
		await acts.perform("canvas.remove_column", { section, column });
		void acts.perform("canvas.select", null);
	};
	return [{ label: __("Remove column"), icon: "lucide-trash-2", onClick: remove }];
}

/** The field panel's acts and Alt+Arrow: the moves, the other tabs, and the panel's remove. */
function fieldMenu(canvas: DesignCanvas, fieldname: string): CanvasMenuOption[] {
	const field = canvas.field(fieldname);
	const options = movesOf(canvas, { kind: "field", fieldname }, FIELD_MOVES);
	const tab = canvas.place(fieldname)?.tab;
	const others = canvas.tabs.value.filter((one) => one.name !== tab);
	if (tab && others.length) {
		const submenu = others.map((one) => ({
			label: one.label || __("Untitled tab"),
			onClick: () => void moveToTab(canvas, fieldname, one.name!),
		}));
		options.push({ label: __("Move to tab"), icon: "lucide-panel-top", submenu });
	}
	const removal = field && removeAction(canvas, field);
	if (field && removal?.label) {
		options.push({ ...removal, onClick: () => void removeField(canvas, field) });
	}
	return options;
}
