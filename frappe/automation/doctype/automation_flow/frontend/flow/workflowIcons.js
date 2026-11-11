const ActionIcon = "lucide-zap";
const AssignIcon = "lucide-user-plus";
const BranchIcon = "lucide-git-branch";
const CreateIcon = "lucide-file-plus";
const EventIcon = "lucide-webhook";
const IncrementIcon = "lucide-trending-up";
const NotifyIcon = "lucide-bell-ring";
const ScriptIcon = "lucide-code";
const SetFieldIcon = "lucide-pencil-line";
const TriggerIcon = "lucide-play";
const WaitIcon = "lucide-timer";
const WebhookIcon = "lucide-webhook";

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

/** One icon and tone per action, so a list of them is scannable rather than eleven zaps. */
const ACTION_STYLES = {
	SetFieldValue: { icon: SetFieldIcon, ...ICON_TONES.blue },
	IncrementFieldValue: { icon: IncrementIcon, ...ICON_TONES.cyan },
	CreateDocument: { icon: CreateIcon, ...ICON_TONES.green },
	SendNotification: { icon: NotifyIcon, ...ICON_TONES.amber },
	AssignToUser: { icon: AssignIcon, ...ICON_TONES.violet },
	CallWebhook: { icon: WebhookIcon, ...ICON_TONES.pink },
	RunScript: { icon: ScriptIcon, ...ICON_TONES.gray },
};

const STEP_STYLES = {
	Action: { icon: ActionIcon, ...ICON_TONES.blue },
	Wait: { icon: WaitIcon, ...ICON_TONES.amber },
	WaitForEvent: { icon: EventIcon, ...ICON_TONES.amber },
	If: { icon: BranchIcon, ...ICON_TONES.green },
};

export const TRIGGER_STYLE = { icon: TriggerIcon, ...ICON_TONES.blue };

export function actionIcon(actionType) {
	return ACTION_STYLES[actionType] || STEP_STYLES.Action;
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
