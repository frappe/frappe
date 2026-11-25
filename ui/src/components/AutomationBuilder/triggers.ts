import { translate as __ } from "../../utils/translate";
import CancelIcon from "~icons/lucide/circle-slash";
import ChangedIcon from "~icons/lucide/pencil-line";
import CreatedIcon from "~icons/lucide/file-plus-corner";
import DeletedIcon from "~icons/lucide/trash-2";
import DateIcon from "~icons/lucide/calendar-clock";
import EventIcon from "~icons/lucide/webhook";
import ManualIcon from "~icons/lucide/hand";
import ScheduleIcon from "~icons/lucide/clock";
import SubmitIcon from "~icons/lucide/send";
import UpdatedIcon from "~icons/lucide/refresh-cw";
import { capabilitiesFor } from "./capabilities";
import { eventIcon } from "./icons";

export const documentTriggers = [
  {
    value: "Doc Created",
    icon: CreatedIcon,
    tone: "blue",
    label: __("Record is created"),
    description: __("Start a run whenever a new record is created."),
  },
  {
    value: "Doc Updated",
    icon: UpdatedIcon,
    tone: "cyan",
    label: __("Record is updated"),
    description: __("Start a run whenever an existing record is saved."),
  },
  {
    value: "Field Value Changed",
    icon: ChangedIcon,
    tone: "violet",
    label: __("Field value changes"),
    description: __("Watch one field and run when it moves to a new value."),
  },
  {
    value: "Doc Deleted",
    icon: DeletedIcon,
    tone: "red",
    label: __("Record is deleted"),
    description: __("Start a run just after a record is deleted."),
  },
  {
    value: "Doc Submitted",
    icon: SubmitIcon,
    tone: "green",
    label: __("Record is submitted"),
    description: __("Start a run when a submittable record is submitted."),
  },
  {
    value: "Doc Cancelled",
    icon: CancelIcon,
    tone: "gray",
    label: __("Record is cancelled"),
    description: __("Start a run when a submitted record is cancelled."),
  },
];

export const otherTriggers = [
  {
    value: "Manual",
    icon: ManualIcon,
    tone: "teal",
    label: __("Launch manually"),
    description: __("Run only when someone starts it from a record."),
  },
  {
    value: "Scheduled",
    icon: ScheduleIcon,
    tone: "amber",
    label: __("On a schedule"),
    description: __("Run on a repeating schedule you define with cron."),
  },
  {
    value: "Date Based",
    icon: DateIcon,
    tone: "orange",
    label: __("On a date"),
    description: __("Run before or after a date stored on the record."),
  },
  {
    value: "Custom Event",
    icon: EventIcon,
    tone: "pink",
    label: __("Custom event"),
    description: __("Run when the app raises a named event you pick."),
  },
];

/**
 * Domain events that are *about* this DocType, as triggers in their own right. The flow still
 * stores them as a Custom Event; naming them here just saves picking the event separately.
 * The value carries the event so picker options stay unique.
 */
export function eventTriggers(doctype) {
  return (capabilitiesFor(doctype)?.trigger_events || []).map((event) => ({
    ...eventIcon(event.value),
    value: `Custom Event:${event.value}`,
    label: event.label,
    description: event.description,
  }));
}

/** The picker value a flow currently sits on. */
export function triggerValue(doc) {
  if (doc?.trigger_type === "Custom Event" && doc.custom_event)
    return `Custom Event:${doc.custom_event}`;
  return doc?.trigger_type || "";
}

/** Split a picker value back into the stored trigger type and event. */
export function triggerFromValue(value) {
  const [type, event = ""] = String(value || "").split(/:(.*)/);
  return { trigger_type: type, custom_event: event };
}

/** Combobox-shaped for the canvas picker; the inspector renders the lists directly. */
export function triggerGroups(doctype) {
  const events = eventTriggers(doctype);
  return [
    { group: __("Records"), options: documentTriggers },
    ...(events.length ? [{ group: __("Activity"), options: events }] : []),
    { group: __("Others"), options: otherTriggers },
  ];
}

/** A Custom Event flow is named by its event, so the trigger node reads as the happening. */
export function triggerDefinition(doc) {
  const value = triggerValue(doc);
  return [
    ...documentTriggers,
    ...otherTriggers,
    ...eventTriggers(doc?.document_type),
  ].find((trigger) => trigger.value === value);
}
