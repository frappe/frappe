import { stepById } from "./flowDoc";
import { nodeAtRow } from "./workflowSteps";

const TRIGGER_FIELDS = new Set([
	"trigger_type",
	"trigger_field",
	"custom_event",
	"date_field",
	"cron_expression",
]);

/** Splits a refused save into messages per node id (`trigger` for the start) and a general one. */
export function saveErrors(error, tree) {
	const errors = {};
	const add = (id, message) => (errors[id] ||= []).push(message);

	for (const field of error?.fieldErrors || []) {
		if (field.parentfield === "actions" && field.idx) {
			const node = nodeAtRow(tree, field.idx);
			if (node) add(node._id, field.message);
		} else if (TRIGGER_FIELDS.has(field.fieldname)) add("trigger", field.message);
	}
	return { errors, general: Object.keys(errors).length ? "" : String(error?.message || "") };
}

/** The errors left after an edit from `before` to `after`: a node that changed loses its own. */
export function withoutEdited(errors, before, after) {
	const kept = {};
	for (const [id, messages] of Object.entries(errors)) {
		if (sameNode(id, before, after)) kept[id] = messages;
	}
	return kept;
}

function sameNode(id, before, after) {
	return JSON.stringify(ownValues(id, before)) === JSON.stringify(ownValues(id, after));
}

// A step's children are nodes with errors of their own; the title and switch are not the trigger's.
function ownValues(id, doc) {
	if (id === "trigger") {
		const { actions, title, enabled, modified, ...trigger } = doc;
		return trigger;
	}
	const { children, ...step } = stepById(doc.actions, id) || {};
	return step;
}
