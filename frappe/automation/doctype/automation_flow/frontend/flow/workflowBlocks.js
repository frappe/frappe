import { __ } from "frappe/i18n";
const BranchIcon = "lucide-git-branch";
const EventIcon = "lucide-webhook";
const WaitIcon = "lucide-timer";
import { actionIcon } from "./workflowIcons";
import { capabilitiesFor } from "./workflowCapabilities";

const flowBlocks = [
	{
		value: "If",
		icon: BranchIcon,
		tone: "green",
		label: __("If / Else"),
		description: __("Split the run into two arms on a condition."),
		values: { step_type: "If" },
	},
	{
		value: "Wait",
		icon: WaitIcon,
		tone: "amber",
		label: __("Wait"),
		description: __("Pause the run for a fixed amount of time."),
		// Seeded, not just shown as a placeholder: the editor's fallback is display-only, so a
		// step the user never opens would save without the unit it appears to have.
		values: { step_type: "Wait", params: JSON.stringify({ unit: "Minutes" }) },
	},
	{
		value: "WaitForEvent",
		icon: EventIcon,
		tone: "amber",
		label: __("Wait for event"),
		description: __("Pause until an event is raised for this record."),
		values: {
			step_type: "WaitForEvent",
			params: JSON.stringify({ timeout_unit: "Days" }),
		},
	},
];

/** Flow control first, then every action the trigger DocType registers, by app. */
export function blockGroups(doctype) {
	const actions = capabilitiesFor(doctype)?.actions || [];
	return [
		{ group: __("Flow"), options: flowBlocks },
		...groupActionsByApp(actions, actionBlock),
	].filter((group) => group.options.length);
}

/** Which app an action came from is the only grouping a long list of them can carry. */
export function groupActionsByApp(actions, toOption) {
	const groups = new Map();
	actions.forEach((action) => {
		const name = groupLabel(action);
		if (!groups.has(name)) groups.set(name, []);
		groups.get(name).push(toOption(action));
	});
	return [...groups].map(([group, options]) => ({ group, options }));
}

/** The framework's actions are the built-in ones; every other app goes by its own name. */
function groupLabel(action) {
	if (action.app === "frappe") return __("Core");
	return shortTitle(action.app_title) || action.app || __("Other");
}

/** App titles carry a vendor prefix the group header does not need. */
function shortTitle(title) {
	return (title || "").replace(/^Frappe\s+/, "");
}

function actionBlock(action) {
	return {
		value: action.action_type,
		...actionIcon(action.action_type),
		label: action.label || action.action_type,
		description: action.description || "",
		values: { step_type: "Action", action_type: action.action_type },
	};
}
