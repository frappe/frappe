import { layoutSteps, toRows, toTree } from "./workflowSteps";

export const FLOW_DOCTYPE = "Automation Flow";

/** A flow before its first save: no DocType and no trigger until the user picks them. */
export function newFlow() {
	return {
		doctype: FLOW_DOCTYPE,
		title: "",
		document_type: "",
		enabled: 0,
		trigger_type: "",
		actions: [],
	};
}

/** The server's flow with its `actions` rows folded into the tree the builder edits. */
export function fromServer(data) {
	const rows = (data.actions || []).map(asText);
	return { ...data, actions: toTree(rows) };
}

/** The document as the server takes it: the tree flattened back into `actions` rows. */
export function toPayload(doc) {
	return { ...doc, actions: toRows(doc.actions) };
}

/** Equal for two documents that save to the same rows, whatever their step ids. */
export function savedKey(doc) {
	return JSON.stringify(toPayload(doc));
}

/** A JSON column may come back parsed; the builder keeps it as the text it edits. */
function asText(row) {
	const text = { ...row };
	for (const field of ["params", "related_condition"]) {
		if (text[field] && typeof text[field] === "object")
			text[field] = JSON.stringify(text[field]);
	}
	return text;
}

/**
 * Hand the step ids of the tree a save came from to the tree the server answered with, so the
 * selected step stays selected. The two trees have the same shape unless the server changed it.
 */
export function keepStepIds(from, to) {
	const before = layoutSteps(from);
	const after = layoutSteps(to);
	if (before.length !== after.length) return;
	after.forEach(({ node }, index) => (node._id = before[index].node._id));
}

/** The step a canvas node id names; null for the trigger node. */
export function stepById(tree, id) {
	return layoutSteps(tree).find(({ node }) => node._id === id)?.node || null;
}
