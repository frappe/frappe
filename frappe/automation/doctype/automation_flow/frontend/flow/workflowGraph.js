import { __ } from "frappe/i18n";
import { actionSchema } from "./workflowCapabilities";
import { TRIGGER_STYLE, stepIcon } from "./workflowIcons";
import { summarizeCondition } from "./workflowConditions";
import { armLabels, isBranching, layoutSteps } from "./workflowSteps";
import { stepIssue, triggerIssue } from "./workflowValidation";
export { workflowEdges } from "./workflowEdges";
import { triggerDefinition } from "./workflowTriggers";

/** `errors` maps a step `_id` (or `trigger`) to the server messages for it. */
export function workflowNodes(doc, errors = {}) {
	const actions = doc.actions || [];
	const tails = tailIds(actions);
	return [
		triggerNode(doc, errors.trigger),
		...layoutSteps(actions).map(({ node, position }) =>
			stepNode(node, position, errors, tails)
		),
	];
}

/** Ids that end a chain - only those grow the flow, so only those offer an add button. */
function tailIds(nodes, ids = new Set()) {
	const tail = nodes[nodes.length - 1];
	if (tail) ids.add(tail._id);
	nodes.forEach((node) => {
		if (!isBranching(node)) return;
		tailIds(node.children.If, ids);
		tailIds(node.children.Else, ids);
	});
	return ids;
}

/** An arm only needs its own button while it is empty - after that its last step has one. */
function openArms(node) {
	if (!isBranching(node)) return undefined;
	const labels = armLabels(node);
	return ["If", "Else"]
		.filter((arm) => !node.children[arm].length)
		.map((arm) => ({ key: arm, label: labels[arm] }));
}

function triggerNode(doc, errors) {
	const trigger = triggerDefinition(doc);
	const { icon, tone } = trigger || TRIGGER_STYLE;
	return {
		id: "trigger",
		position: { x: 0, y: 0 },
		data: {
			icon,
			tone,
			start: true,
			terminal: !doc.actions?.length,
			empty: !doc.trigger_type,
			kicker: __("Trigger"),
			label: trigger?.label || __("Start from scratch"),
			detail: doc.trigger_type
				? __("on {0}", [doc.document_type])
				: __("Pick initial trigger"),
			issue: issueOf(triggerIssue(doc), errors?.join("\n")),
		},
	};
}

/** How a step reads on a card: its icon and the three lines around it. */
export function stepPresentation(node) {
	return {
		...stepIcon(node),
		kicker: kickerFor(node),
		label: labelFor(node),
		detail: detailFor(node),
	};
}

function stepNode(node, position, errors, tails = new Set()) {
	const arms = openArms(node);
	return {
		id: node._id,
		position,
		data: {
			...stepPresentation(node),
			branching: isBranching(node),
			arms,
			// Continuing past a branch only makes sense once both arms lead somewhere.
			canContinue: isBranching(node) && tails.has(node._id) && !arms.length,
			terminal: tails.has(node._id),
			issue: issueOf(stepIssue(node), errors[node._id]?.join("\n")),
		},
	};
}

/** A server error outranks a missing setting: the first blocks the save, the second the run. */
function issueOf(setup, error) {
	if (error) return { level: "error", message: error };
	return setup ? { level: "warning", message: setup } : undefined;
}

function kickerFor(node) {
	if (node.step_type === "If") return __("Condition");
	if (node.step_type === "WaitForEvent") return __("Wait for");
	if (node.step_type === "Wait") return __("Wait");
	return node.target && node.target !== "trigger"
		? __("Action on {0}", [node.target])
		: __("Action");
}

/** Nodes read as sentences, not class names - the canvas is the first thing anyone scans. */
function labelFor(node) {
	if (node.step_type === "If")
		return node.step_condition
			? summarizeCondition(node.step_condition)
			: __("Set a condition");
	if (node.step_type === "Wait") return waitLabel(node);
	if (node.step_type === "WaitForEvent") return eventLabel(node);
	return actionLabel(node);
}

function waitLabel(node) {
	const { value, unit } = parseParams(node);
	return value ? __("Wait {0} {1}", [value, unit || "Minutes"]) : __("Pause the run");
}

function eventLabel(node) {
	const { event_name: event } = parseParams(node);
	return event ? prettyEvent(event) : __("Pick an event");
}

/** `crm.prospect_message_received` reads as "Prospect message received". */
function prettyEvent(event) {
	const words = String(event).split(".").pop().replace(/_/g, " ");
	return words.charAt(0).toUpperCase() + words.slice(1);
}

function actionLabel(node) {
	if (!node.action_type) return __("Configure action");
	const schema = actionSchema(null, node.action_type);
	return schema?.label || node.action_type;
}

function detailFor(node) {
	if (node.step_type !== "Action" || !node.action_type) return "";
	return paramSummary(actionSchema(null, node.action_type), parseParams(node));
}

const SUMMARY_FIELDTYPES = ["Data", "Select", "Link", "Int", "Float", "Currency", "Percent"];

/** The first couple of simple params, so "Set Lead Temperature" becomes "…: Warm". */
function paramSummary(schema, params) {
	return (schema?.params_schema || [])
		.filter((field) => SUMMARY_FIELDTYPES.includes(field.fieldtype))
		.map((field) => params[field.fieldname])
		.filter((value) => value !== undefined && value !== null && value !== "")
		.slice(0, 2)
		.join(", ");
}

function parseParams(node) {
	try {
		return JSON.parse(node.params || "{}");
	} catch {
		return {};
	}
}
