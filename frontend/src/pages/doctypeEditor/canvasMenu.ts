// The "⋯" menu of a column or section on the canvas: the moves Alt+Arrow makes, then the item's
// own acts. And the click that selects one.
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { canvasMove, type Direction } from "./canvasMoves";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";
import { fetchAsked } from "./fetchFrom";

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
		const remove = { label: __("Remove from layout"), icon: "lucide-eye-off", onClick: run("canvas.unplace_field", item) };
		return [remove, ...fetchActs(canvas, item)];
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

/** On a Link field: "Fetch a field…" selects it and opens the field panel's picker. */
function fetchActs(canvas: DesignCanvas, item: { kind: "field"; fieldname: string }): CanvasMenuOption[] {
	const field = canvas.field(item.fieldname);
	if (field?.fieldtype !== "Link" || !field.options) return [];
	const ask = async () => {
		const menuClosed = menuGivesFocusBack();
		await acts.perform("canvas.select", item);
		await menuClosed;
		fetchAsked.value = item.fieldname;
	};
	return [{ label: __("Fetch a field…"), icon: "lucide-plus", onClick: () => void ask() }];
}

// The closing menu puts focus back on its ⋯ a frame or more later, and a picker already open
// would read that as a focus outside and close. 300 ms covers a menu that never gives it back.
function menuGivesFocusBack(): Promise<void> {
	return new Promise((resolve) => {
		const done = () => {
			document.removeEventListener("focusin", done);
			clearTimeout(timer);
			resolve();
		};
		const timer = setTimeout(done, 300);
		document.addEventListener("focusin", done);
	});
}
