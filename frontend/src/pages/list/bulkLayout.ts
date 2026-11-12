// Where the bulk bar draws each action: transitions and buttons in the bar, the rest grouped in More.
import { __ } from "@/i18n";
import type { BulkGroup } from "@/listPage/types";

export interface BulkEntry {
	name: string;
	label: string;
	icon?: string;
	/** The built-in's More group; absent on a script's item, which is an app action. */
	group?: BulkGroup;
	button?: boolean;
	disabled?: boolean;
	onClick: () => void;
}

export interface BulkMenuOption {
	label: string;
	icon?: string;
	theme?: "red";
	disabled?: boolean;
	onClick: () => void;
}

export interface BulkMenuGroup {
	group: string;
	theme?: "red";
	options: BulkMenuOption[];
}

export interface BulkLayout {
	/** The first buttons: the workflow transitions, while there are at most two. */
	transitions: BulkEntry[];
	buttons: BulkEntry[];
	menu: BulkMenuGroup[];
	/** Delete as a red icon after More; it also sits in the danger group. */
	trash?: BulkEntry;
}

/** The transitions that stay buttons; more than this move into More's Workflow group. */
export const TRANSITION_BUTTONS = 2;

export function layoutBulk(entries: BulkEntry[], doctype: string): BulkLayout {
	const workflow = entries.filter((entry) => entry.group === "workflow");
	const transitions = workflow.length > TRANSITION_BUTTONS ? [] : workflow;
	const buttons = entries.filter((entry) => entry.button && entry.group !== "workflow");
	return {
		transitions,
		buttons,
		menu: menuGroups(entries, doctype, workflow.length > TRANSITION_BUTTONS),
		trash: entries.find((entry) => entry.name === "delete"),
	};
}

function menuGroups(entries: BulkEntry[], doctype: string, workflowInMenu: boolean): BulkMenuGroup[] {
	const groups: [BulkGroup | undefined, string][] = [
		[undefined, __(doctype)],
		...(workflowInMenu ? [["workflow", __("Workflow")] as [BulkGroup, string]] : []),
		["collaborate", __("Assign, tag and share")],
		["output", __("Print and export")],
		["danger", __("Submit, cancel and delete")],
	];
	return groups
		.map(([group, label]) => ({
			group: label,
			theme: group === "danger" ? ("red" as const) : undefined,
			options: entries
				.filter((entry) => entry.group === group && (!entry.button || group === "workflow"))
				.map((entry) => menuOption(entry, group === "danger")),
		}))
		.filter((group) => group.options.length);
}

function menuOption(entry: BulkEntry, danger: boolean): BulkMenuOption {
	return {
		label: entry.label,
		icon: entry.icon,
		theme: danger ? "red" : undefined,
		disabled: entry.disabled,
		onClick: entry.onClick,
	};
}
