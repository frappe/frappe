import { actionSchema } from "./workflowCapabilities";

const ActionIcon = "lucide-zap";
const BranchIcon = "lucide-git-branch";
const EventIcon = "lucide-webhook";
const TriggerIcon = "lucide-play";
const WaitIcon = "lucide-timer";

/** `tone` colours a bare glyph on a node card. */
export const ICON_TONES = {
	blue: { tone: "blue" },
	green: { tone: "green" },
	teal: { tone: "teal" },
	amber: { tone: "amber" },
	violet: { tone: "violet" },
	cyan: { tone: "cyan" },
	orange: { tone: "orange" },
	pink: { tone: "pink" },
	red: { tone: "red" },
	gray: { tone: "gray" },
	purple: { tone: "purple" },
};

/** An action's glyph comes from the server (its `icon`); only the tone is chosen here. */
const ACTION_TONES = {
	SetFieldValue: "blue",
	IncrementFieldValue: "cyan",
	CreateDocument: "green",
	SendNotification: "amber",
	AssignToUser: "violet",
	CallWebhook: "pink",
	RunScript: "gray",
};

const STEP_STYLES = {
	Action: { icon: ActionIcon, ...ICON_TONES.blue },
	Wait: { icon: WaitIcon, ...ICON_TONES.amber },
	WaitForEvent: { icon: EventIcon, ...ICON_TONES.amber },
	If: { icon: BranchIcon, ...ICON_TONES.green },
};

export const TRIGGER_STYLE = { icon: TriggerIcon, ...ICON_TONES.blue };

export function actionIcon(actionType) {
	const icon = actionSchema(null, actionType)?.icon || ActionIcon;
	return { icon, ...ICON_TONES[ACTION_TONES[actionType] || "blue"] };
}

/** An event trigger wears the icon its registrant gave it. */
export function eventIcon(event) {
	return { icon: event?.icon || EventIcon, ...ICON_TONES.pink };
}

export function stepTypeIcon(stepType) {
	return STEP_STYLES[stepType] || STEP_STYLES.Action;
}

/** An action step wears the icon of the action it runs, not a generic bolt. */
export function stepIcon(step) {
	return step.step_type === "Action"
		? actionIcon(step.action_type)
		: stepTypeIcon(step.step_type);
}
