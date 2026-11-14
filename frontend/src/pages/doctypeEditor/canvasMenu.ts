// The "⋯" menu of a section on the canvas: the moves Alt+Arrow makes, then the item's
// own acts. And the click that selects one.
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { canvasMove, type Direction } from "./canvasMoves";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";

/** A read-only canvas may be a view beside the editor's own, so it selects on itself. */
export function selectOn(canvas: DesignCanvas, selection: CanvasSelection) {
	if (!canvas.editable) return canvas.select(selection);
	void acts.perform("canvas.select", selection);
}

export interface CanvasMenuOption {
	label: string;
	icon: string;
	disabled?: boolean;
	onClick: () => void;
}

/** Only a section has a "⋯" menu: a field has the bin and its marks, a tab and a column their panel. */
export type MenuItem = Extract<CanvasSelection, { kind: "section" }>;

export function canvasMenu(canvas: DesignCanvas, item: MenuItem): CanvasMenuOption[] {
	const moves = MOVES.map(([direction, label, icon]) => {
		const move = canvasMove(canvas.tabs.value, item, direction);
		return { label, icon, disabled: !move, onClick: () => move && acts.perform(move.act, move.value) };
	});
	return [...moves, ...ownActs(item)];
}

const MOVES: [Direction, string, string][] = [
	["up", __("Move up"), "lucide-arrow-up"],
	["down", __("Move down"), "lucide-arrow-down"],
	["left", __("Move to the tab before"), "lucide-arrow-left"],
	["right", __("Move to the tab after"), "lucide-arrow-right"],
];

function ownActs(item: MenuItem): CanvasMenuOption[] {
	const run = (act: string, value: unknown) => () => void acts.perform(act, value);
	return [
		{ label: __("Add column"), icon: "lucide-columns-2", onClick: run("canvas.add_column", { section: item.section }) },
		{ label: __("Remove section"), icon: "lucide-trash-2", onClick: run("canvas.remove_section", { section: item.section }) },
	];
}
