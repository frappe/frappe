// The Details canvas's acts. Drag, Alt+Arrow, the menus and the palette all run these, so each
// change stages through one path; an act's value is the keys of the edit it stages.
import type { ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { DETAILS, type CanvasSelection, type DesignCanvas } from "./designCanvas";
import { fieldnameFromLabel } from "./fieldRules";
import type { EditorActsHost } from "./editorActs";

type Keys = Record<string, unknown>;

export function canvasItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const when = () => editing(host);
	const staging: [name: string, label: string][] = [
		["remove_tab", __("Remove tab")],
		["move_tab", __("Move tab")],
		["remove_section", __("Remove section")],
		["move_section", __("Move section")],
		["add_column", __("Add column")],
		["remove_column", __("Remove column")],
		["move_column", __("Move column")],
		["place_field", __("Place field")],
		["move_field", __("Move field")],
		["unplace_field", __("Remove from layout")],
		["set_container_property", __("Set a container property")],
	];
	const staged = staging.map(([name, label]) => ({
		name,
		label,
		palette: false as const,
		when,
		run: (_context: EditorActsHost, keys: Keys) => stage(host, `canvas.${name}`, keys),
	}));
	return [
		{
			name: "add_tab",
			label: __("Add tab"),
			icon: "plus",
			when,
			run: (_context, keys?: Keys) => {
				const canvas = host.canvas()!;
				const added = adds(canvas, () => stage(host, "canvas.add_tab", keys ?? {}), tabNames);
				if (added) canvas.select({ kind: "tab", tab: added });
			},
		},
		{
			name: "add_section",
			label: __("Add section"),
			icon: "plus",
			when,
			run: (_context, keys?: Keys) => {
				const canvas = host.canvas()!;
				const into = keys ?? { tab: canvas.openTab.value?.name };
				const added = adds(canvas, () => stage(host, "canvas.add_section", into), sectionNames);
				if (added) canvas.select({ kind: "section", section: added });
			},
		},
		...staged,
		{
			name: "select",
			label: __("Select"),
			palette: false,
			when: () => Boolean(host.canvas()),
			run: (_context, selection: CanvasSelection | null) => host.canvas()!.select(selection),
		},
	];
}

/** The `fields` acts the canvas needs; the field panel adds the rest. */
export function fieldItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	return [
		{
			name: "add_field",
			label: __("Add field"),
			icon: "plus",
			key: "A",
			when: () => editing(host),
			run: (_context, keys?: Keys & { label: string; fieldname?: string }) => {
				const canvas = host.canvas()!;
				if (!keys) return void (canvas.adding.value = canvas.targetSection());
				const placed = "section" in keys || "tab" in keys;
				canvas.stage({ ...keys, act: "fields.add_field", ...(placed ? { layout: DETAILS } : {}) });
				canvas.select({ kind: "field", fieldname: keys.fieldname || fieldnameFromLabel(keys.label) });
			},
		},
	];
}

function editing(host: EditorActsHost) {
	return host.tab.value === "editor" && Boolean(host.canvas()?.editable);
}

function stage(host: EditorActsHost, act: string, keys: Keys) {
	host.canvas()!.stage({ ...keys, act, layout: DETAILS });
}

/** The name the staging added, found by the names before and after. */
function adds(canvas: DesignCanvas, staging: () => void, names: (canvas: DesignCanvas) => string[]) {
	const before = new Set(names(canvas));
	staging();
	return names(canvas).find((name) => !before.has(name));
}

function tabNames(canvas: DesignCanvas) {
	return canvas.tabs.value.map((tab) => tab.name!);
}

function sectionNames(canvas: DesignCanvas) {
	return canvas.tabs.value.flatMap((tab) => tab.sections.map((section) => section.name!));
}
