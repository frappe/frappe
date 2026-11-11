import { __ } from "frappe/i18n";
import { actionSchema } from "./workflowCapabilities";
import { TRIGGER_STYLE, stepIcon } from "./workflowIcons";
import { summarizeCondition } from "./workflowConditions";
import { armLabels, isBranching, layoutSteps } from "./workflowSteps";
import { stepIssue, triggerIssue } from "./workflowValidation";
export { workflowEdges } from "./workflowEdges";
import { triggerDefinition } from "./workflowTriggers";

export function workflowNodes(doc, errors = {}) {
	const actions = doc.actions || [];
	const tails = tailIds(actions);
	return [
		triggerNode(doc),
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
	if (!isBranching(node)) return null;
	const labels = armLabels(node);
	return ["If", "Else"]
		.filter((arm) => !node.children[arm].length)
		.map((arm) => ({ branch: arm, label: labels[arm] }));
}

function triggerNode(doc) {
	const trigger = triggerDefinition(doc);
	return {
		id: "trigger",
		type: "automation",
		position: { x: 0, y: 0 },
		data: {
			...TRIGGER_STYLE,
			...(trigger || {}),
			isTrigger: true,
			empty: !doc.trigger_type,
			kicker: __("Trigger"),
			label: trigger?.label || __("Start from scratch"),
			detail: doc.trigger_type
				? __("on {0}", [doc.document_type])
				: __("Pick initial trigger"),
			incomplete: triggerIssue(doc),
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
		type: "automation",
		position,
		data: {
			step: node,
			...stepPresentation(node),
			branching: isBranching(node),
			arms,
			// Continuing past a branch only makes sense once both arms lead somewhere.
			canContinue: isBranching(node) && tails.has(node._id) && !arms.length,
			last: tails.has(node._id),
			error: Boolean(errors[node._id]?.length),
			incomplete: stepIssue(node),
		},
	};
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
