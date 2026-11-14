// The "⋯" menu of a column or section on the canvas: the moves Alt+Arrow makes, then the item's
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

/** Fields and tabs have no "⋯" menu: a field has the bin and its marks, a tab its panel. */
export type MenuItem = Extract<CanvasSelection, { kind: "section" | "column" }>;

export function canvasMenu(canvas: DesignCanvas, item: MenuItem): CanvasMenuOption[] {
	const moves = moveLabels(item.kind).map(([direction, label, icon]) => {
		const move = canvasMove(canvas.tabs.value, item, direction);
		return { label, icon, disabled: !move, onClick: () => move && acts.perform(move.act, move.value) };
	});
	return [...moves, ...ownActs(canvas, item)];
}

function moveLabels(kind: MenuItem["kind"]): [Direction, string, string][] {
	if (kind === "section") {
		return [
			["up", __("Move up"), "lucide-arrow-up"],
			["down", __("Move down"), "lucide-arrow-down"],
			["left", __("Move to the tab before"), "lucide-arrow-left"],
			["right", __("Move to the tab after"), "lucide-arrow-right"],
		];
	}
	return [
		["left", __("Move left"), "lucide-arrow-left"],
		["right", __("Move right"), "lucide-arrow-right"],
	];
}

function ownActs(canvas: DesignCanvas, item: MenuItem): CanvasMenuOption[] {
	const run = (act: string, value: unknown) => () => void acts.perform(act, value);
	if (item.kind === "section") {
		return [
			{ label: __("Add column"), icon: "lucide-columns-2", onClick: run("canvas.add_column", { section: item.section }) },
			{ label: __("Remove section"), icon: "lucide-trash-2", onClick: run("canvas.remove_section", { section: item.section }) },
		];
	}
	const section = canvas.tabs.value.flatMap((tab) => tab.sections).find((one) => one.name === item.section);
	return [
		{
			label: __("Remove column"),
			icon: "lucide-trash-2",
			disabled: (section?.columns.length ?? 0) < 2,
			onClick: run("canvas.remove_column", { section: item.section, column: item.column }),
		},
	];
}
