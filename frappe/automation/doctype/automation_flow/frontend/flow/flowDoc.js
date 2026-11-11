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

/** The query key naming the flow a new flow copies. */
export const COPY_OF = "__copy_of";

/** The name of the flow the address asks to copy, or null. */
export function copySource(query) {
	return [query?.[COPY_OF]].flat()[0] || null;
}

/**
 * A flow before its first save: the server's copy of another flow when there is one, under the
 * values the address carries (what "Edit full form" hands over).
 */
export function openingFlow(copy, query = {}) {
	const flow = copy ? fromServer(copy) : newFlow();
	for (const field of ["title", "document_type", "trigger_type", "enabled"]) {
		const given = [query[field]].flat()[0];
		if (typeof given === "string") flow[field] = field === "enabled" ? Number(given) : given;
	}
	return flow;
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

/** Carry step ids onto the tree the server answered with, so the selection survives a save. */
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
