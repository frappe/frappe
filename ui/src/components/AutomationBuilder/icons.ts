import type { Component } from "vue";
import ActionIcon from "~icons/lucide/zap";
import AssignIcon from "~icons/lucide/user-plus";
import BranchIcon from "~icons/lucide/git-branch";
import CreateIcon from "~icons/lucide/file-plus";
import EventIcon from "~icons/lucide/webhook";
import IncrementIcon from "~icons/lucide/trending-up";
import NotifyIcon from "~icons/lucide/bell-ring";
import ScriptIcon from "~icons/lucide/code";
import SetFieldIcon from "~icons/lucide/pencil-line";
import TriggerIcon from "~icons/lucide/play";
import WaitIcon from "~icons/lucide/timer";
import WebhookIcon from "~icons/lucide/webhook";
import type { AutomationCanvasTone } from "../AutomationCanvas/types";

export interface AutomationStyle {
  icon: string | Component;
  tone: AutomationCanvasTone;
}

export interface AutomationStyles {
  /** By action type, for actions an app registers. */
  actions?: Record<string, AutomationStyle>;
  /** By event name, for the trigger events an app raises. */
  events?: Record<string, AutomationStyle>;
}

/** One icon and tone per action, so a list of them is scannable rather than eleven zaps. */
const ACTION_STYLES: Record<string, AutomationStyle> = {
  SetFieldValue: { icon: SetFieldIcon, tone: "blue" },
  IncrementFieldValue: { icon: IncrementIcon, tone: "cyan" },
  CreateDocument: { icon: CreateIcon, tone: "green" },
  SendNotification: { icon: NotifyIcon, tone: "amber" },
  AssignToUser: { icon: AssignIcon, tone: "violet" },
  CallWebhook: { icon: WebhookIcon, tone: "pink" },
  RunScript: { icon: ScriptIcon, tone: "gray" },
};

const EVENT_STYLES: Record<string, AutomationStyle> = {};

const STEP_STYLES: Record<string, AutomationStyle> = {
  Action: { icon: ActionIcon, tone: "blue" },
  Wait: { icon: WaitIcon, tone: "amber" },
  WaitForEvent: { icon: EventIcon, tone: "amber" },
  If: { icon: BranchIcon, tone: "green" },
};

export const TRIGGER_STYLE: AutomationStyle = {
  icon: TriggerIcon,
  tone: "blue",
};

/** Apps style the actions and events they add; anything unstyled falls back to a generic icon. */
export function registerAutomationStyles(styles: AutomationStyles) {
  Object.assign(ACTION_STYLES, styles.actions);
  Object.assign(EVENT_STYLES, styles.events);
}

export function actionIcon(actionType: string): AutomationStyle {
  return ACTION_STYLES[actionType] || STEP_STYLES.Action;
}

export function eventIcon(eventName: string): AutomationStyle {
  return EVENT_STYLES[eventName] || { icon: EventIcon, tone: "pink" };
}

export function stepTypeIcon(stepType: string): AutomationStyle {
  return STEP_STYLES[stepType] || STEP_STYLES.Action;
}

/** An action step wears the icon of the action it runs, not a generic bolt. */
export function stepIcon(step: { step_type: string; action_type?: string }) {
  return step.step_type === "Action"
    ? actionIcon(step.action_type || "")
    : stepTypeIcon(step.step_type);
}
