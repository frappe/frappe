// The "⋯" menu of a field, column, section or tab on the canvas: the moves Alt+Arrow makes, then
// the item's own acts.
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { canvasMove, type Direction } from "./canvasMoves";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";

export interface CanvasMenuOption {
	label: string;
	icon: string;
	disabled?: boolean;
	onClick: () => void;
}

export function canvasMenu(canvas: DesignCanvas, item: CanvasSelection): CanvasMenuOption[] {
	const moves = moveLabels(item.kind).map(([direction, label, icon]) => {
		const move = canvasMove(canvas.tabs.value, item, direction);
		return { label, icon, disabled: !move, onClick: () => move && acts.perform(move.act, move.value) };
	});
	return [...moves, ...ownActs(canvas, item)];
}

function moveLabels(kind: CanvasSelection["kind"]): [Direction, string, string][] {
	const vertical: [Direction, string, string][] = [
		["up", __("Move up"), "lucide-arrow-up"],
		["down", __("Move down"), "lucide-arrow-down"],
	];
	if (kind === "field") {
		return [
			...vertical,
			["left", __("Move to the column before"), "lucide-arrow-left"],
			["right", __("Move to the column after"), "lucide-arrow-right"],
		];
	}
	if (kind === "section") {
		return [
			...vertical,
			["left", __("Move to the tab before"), "lucide-arrow-left"],
			["right", __("Move to the tab after"), "lucide-arrow-right"],
		];
	}
	return [
		["left", __("Move left"), "lucide-arrow-left"],
		["right", __("Move right"), "lucide-arrow-right"],
	];
}

function ownActs(canvas: DesignCanvas, item: CanvasSelection): CanvasMenuOption[] {
	const run = (act: string, value: unknown) => () => void acts.perform(act, value);
	if (item.kind === "field") {
		return [{ label: __("Remove from layout"), icon: "lucide-eye-off", onClick: run("canvas.unplace_field", item) }];
	}
	if (item.kind === "section") {
		return [
			{ label: __("Add column"), icon: "lucide-columns-2", onClick: run("canvas.add_column", { section: item.section }) },
			{ label: __("Remove section"), icon: "lucide-trash-2", onClick: run("canvas.remove_section", { section: item.section }) },
		];
	}
	if (item.kind === "column") {
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
	return [
		{
			label: __("Remove tab"),
			icon: "lucide-trash-2",
			disabled: canvas.tabs.value.length < 2,
			onClick: run("canvas.remove_tab", { tab: item.tab }),
		},
	];
}
