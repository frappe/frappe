import { nodeAtRow } from "./workflowSteps";

const ROW_ERROR = /Row (\d+):\s*([^\n<]*)/g;
const TRIGGER_FIELDS = new Set([
	"trigger_type",
	"trigger_field",
	"custom_event",
	"date_field",
	"cron_expression",
]);

/**
 * Splits a refused save into messages for nodes and one for the flow. The server names a failing
 * step as "Row N: ..." and N counts the rows `toRows` wrote, so `nodeAtRow` finds its node.
 * `errors` maps a node id (`trigger` for the start node) to its messages.
 */
export function saveErrors(error, tree) {
	const errors = {};
	const add = (id, message) => (errors[id] ||= []).push(message);
	const message = String(error?.message || "");

	for (const [, row, text] of message.matchAll(ROW_ERROR)) {
		const node = nodeAtRow(tree, Number(row));
		if (node) add(node._id, text.trim());
	}
	for (const field of error?.fieldErrors || []) {
		if (field.parentfield === "actions" && field.idx) {
			const node = nodeAtRow(tree, field.idx);
			if (node) add(node._id, field.message);
		} else if (TRIGGER_FIELDS.has(field.fieldname)) add("trigger", field.message);
	}
	return { errors, general: Object.keys(errors).length ? "" : message };
}
