import { __ } from "frappe/i18n";
import { actionSchema, stepParams } from "./workflowCapabilities";
import { toRows } from "./workflowSteps";

const TRIGGER_REQUIREMENTS = {
	"Field Value Changed": {
		field: "trigger_field",
		label: __("a field to watch"),
	},
	Scheduled: { field: "cron_expression", label: __("a schedule") },
	"Date Based": { field: "date_field", label: __("a date field") },
	"Custom Event": { field: "custom_event", label: __("an event") },
};

/** What the trigger still needs before the flow can start. Empty once it is ready. */
export function triggerIssue(doc) {
	if (!doc.trigger_type) return "";
	const required = TRIGGER_REQUIREMENTS[doc.trigger_type];
	if (!required || !isBlank(doc[required.field])) return "";
	return __("Pick {0}", [required.label]);
}

/** What a step still needs before the flow can run it. Empty once it is ready. */
export function stepIssue(step) {
	if (step.step_type === "If") return step.step_condition ? "" : __("Set a condition");
	if (step.step_type === "Wait") return stepParams(step).value ? "" : __("Set how long to wait");
	if (step.step_type === "WaitForEvent")
		return stepParams(step).event_name ? "" : __("Pick an event");
	return actionIssue(step);
}

function actionIssue(step) {
	if (!step.action_type) return __("Pick an action");
	if (step.action_type === "SetFieldValue") return setFieldIssue(step);
	return missingParamIssue(step);
}

function setFieldIssue(step) {
	const params = stepParams(step);
	return params.field || hasValues(params.values) ? "" : __("Choose a field to set");
}

function missingParamIssue(step) {
	const params = stepParams(step);
	const missing = (actionSchema(null, step.action_type)?.params_schema || [])
		.filter((param) => param.reqd)
		.find((param) => isEmpty(params[param.fieldname]));
	return missing ? __("{0} is required", [missing.label]) : "";
}

/** The first row the flow cannot run, so a save can point at the step that blocks it. */
export function firstBlockingRow(actions) {
	return toRows(actions)
		.map((row) => ({ row, issue: stepIssue(row) }))
		.find(({ issue }) => issue);
}

export function hasValues(value) {
	if (!value) return false;
	if (Array.isArray(value)) return value.length > 0;
	if (typeof value === "object") return Object.keys(value).length > 0;
	return true;
}

function isBlank(value) {
	return value === undefined || value === null || value === "";
}

/** A JSON param reaches here as a list, an object, or the JSON text the builder saved -
    an empty one of any of those is still an unanswered required field. */
function isEmpty(value) {
	if (isBlank(value)) return true;
	if (typeof value === "object") return !hasValues(value);
	return ["[]", "{}"].includes(String(value).trim());
}
