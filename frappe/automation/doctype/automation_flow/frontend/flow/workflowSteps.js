import { __ } from "frappe/i18n";
/**
 * Steps are stored flat (`parent_step` = `idx` of the `If` row, plus `branch`) and edited as a tree,
 * flattened on save so each parent precedes its children.
 */

// The canvas runs left to right: each step is a column, an If's arms split vertically.
const COLUMN_WIDTH = 300;
const BRANCH_OFFSET = 108;

/** A wait-for-event is two rows (the wait, then an `If` on its outcome) shown as one node. */
export const EVENT_MATCHED = 'context.get("event", {}).get("outcome") == "Matched"';

let uid = 0;

/** Steps that own an If and an Else arm. */
export function isBranching(node) {
	return node?.step_type === "If" || node?.step_type === "WaitForEvent";
}

export function armLabels(node) {
	return node?.step_type === "WaitForEvent"
		? { If: __("Event happened"), Else: __("Timed out") }
		: { If: __("True"), Else: __("False") };
}

function hasArms(node) {
	return Boolean(node.children?.If.length || node.children?.Else.length);
}

export function newStep(values = {}) {
	return {
		_id: `step-${++uid}`,
		doctype: "Automation Action",
		step_type: "Action",
		action_type: "",
		step_key: "",
		target: "trigger",
		output_alias: "",
		params: "{}",
		step_condition: "",
		related_condition: "",
		children: { If: [], Else: [] },
		...values,
	};
}

export function toTree(rows = []) {
	const nodes = rows.map((row) => newStep({ ...row, children: { If: [], Else: [] } }));
	const byIdx = new Map(nodes.map((node, index) => [rowIdx(rows[index], index), node]));
	const roots = [];
	nodes.forEach((node, index) => {
		const parent = rows[index].parent_step && byIdx.get(rows[index].parent_step);
		if (parent) parent.children[armOf(rows[index])].push(node);
		else roots.push(node);
	});
	collapseOutcomeSteps(roots);
	return roots;
}

/** Fold each `If` that only reads a preceding wait's outcome back into that wait. */
function collapseOutcomeSteps(nodes) {
	for (let index = nodes.length - 1; index >= 0; index--) {
		const node = nodes[index];
		if (isBranching(node)) {
			collapseOutcomeSteps(node.children.If);
			collapseOutcomeSteps(node.children.Else);
		}
		const outcome = nodes[index + 1];
		if (!isOutcomeOf(node, outcome)) continue;
		node.children = outcome.children;
		node._outcomeKey = outcome.step_key;
		nodes.splice(index + 1, 1);
	}
}

function isOutcomeOf(node, next) {
	return (
		node?.step_type === "WaitForEvent" &&
		next?.step_type === "If" &&
		next.step_condition === EVENT_MATCHED
	);
}

export function toRows(tree) {
	const rows = [];
	appendRows(tree, rows, 0, "");
	return rows;
}

/** Step keys name steps in run logs and must be unique; untitled steps get one from their action. */
export function defaultStepKey(node, taken = new Set()) {
	const base = scrub(node.action_type || KEY_BASES[node.step_type] || node.step_type);
	let key = base;
	let suffix = 2;
	while (taken.has(key)) key = `${base}_${suffix++}`;
	return key;
}

const KEY_BASES = {
	If: "condition",
	Wait: "wait",
	WaitForEvent: "wait_for_event",
};

function scrub(text) {
	return String(text || "step")
		.replace(/([a-z\d])([A-Z])/g, "$1_$2")
		.replace(/\W+/g, "_")
		.toLowerCase();
}

/** Stamp the keys a save handed back onto the tree it came from. */
export function adoptRowKeys(tree, rows) {
	takeRowKeys(tree, [...rows]);
}

/** Walks the tree in the order `appendRows` wrote it, so rows line up with nodes. */
function takeRowKeys(nodes, queue) {
	nodes.forEach((node) => {
		const row = queue.shift();
		if (!row) return;
		node.step_key = row.step_key;
		node.idx = row.idx;
		if (!isBranching(node) || !hasArms(node)) return;
		if (node.step_type === "WaitForEvent") node._outcomeKey = queue.shift()?.step_key;
		takeRowKeys(node.children.If, queue);
		takeRowKeys(node.children.Else, queue);
	});
}

function appendRows(nodes, rows, parentIdx, branch, taken = new Set()) {
	nodes.forEach((node) => {
		const { children, ...row } = node;
		delete row._id;
		delete row._outcomeKey;
		row.step_key = row.step_key || defaultStepKey(node, taken);
		taken.add(row.step_key);
		rows.push({
			...row,
			idx: rows.length + 1,
			parent_step: parentIdx,
			branch: parentIdx ? branch : "",
		});
		let idx = rows.length;
		if (!isBranching(node) || !hasArms(node)) return;
		if (node.step_type === "WaitForEvent") {
			const outcome = outcomeRow(node, rows.length + 1, parentIdx, branch, taken);
			taken.add(outcome.step_key);
			rows.push(outcome);
			idx = rows.length;
		}
		appendRows(children.If, rows, idx, "If", taken);
		appendRows(children.Else, rows, idx, "Else", taken);
	});
}

/** The `If` that turns a wait's recorded outcome into two arms. */
function outcomeRow(node, idx, parentIdx, branch, taken) {
	const key = node._outcomeKey || `${node.step_key || "wait"}_outcome`;
	return {
		doctype: "Automation Action",
		step_type: "If",
		step_key: taken.has(key) ? `${key}_2` : key,
		action_type: "",
		target: "trigger",
		output_alias: "",
		params: "{}",
		step_condition: EVENT_MATCHED,
		related_condition: "",
		idx,
		parent_step: parentIdx,
		branch: parentIdx ? branch : "",
	};
}

/** The node a flattened row (1-based `idx`) belongs to, walked in the order `appendRows` writes. */
export function nodeAtRow(tree, rowIndex) {
	return findRow(tree, { next: 1, target: rowIndex });
}

function findRow(nodes, cursor) {
	for (const node of nodes) {
		if (cursor.next++ === cursor.target) return node;
		if (!isBranching(node) || !hasArms(node)) continue;
		if (node.step_type === "WaitForEvent" && cursor.next++ === cursor.target) return node;
		const found = findRow(node.children.If, cursor) || findRow(node.children.Else, cursor);
		if (found) return found;
	}
	return null;
}

/** Depth-first list of every node with its canvas position. Unlike `toRows`, it has no outcome rows. */
export function layoutSteps(tree) {
	const placed = [];
	place(tree, COLUMN_WIDTH, 0, placed);
	return placed;
}

// Arms of a nested If sit closer together than their parent's, keeping nested branches compact.
function place(nodes, x, y, placed, spread = BRANCH_OFFSET) {
	nodes.forEach((node) => {
		placed.push({ node, position: { x, y } });
		x += COLUMN_WIDTH;
		if (!isBranching(node)) return;
		const ifEnd = place(node.children.If, x, y - spread, placed, spread / 2);
		const elseEnd = place(node.children.Else, x, y + spread, placed, spread / 2);
		x = Math.max(ifEnd, elseEnd);
	});
	return x;
}

/** The array a node lives in, so callers can insert a sibling or splice it out. */
export function listOf(tree, node) {
	if (tree.includes(node)) return tree;
	for (const candidate of tree) {
		if (!isBranching(candidate)) continue;
		const found = listOf(candidate.children.If, node) || listOf(candidate.children.Else, node);
		if (found) return found;
	}
	return null;
}

export function removeStep(tree, nodeOrId) {
	const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId?._id;
	const node = layoutSteps(tree).find(({ node }) => node._id === id)?.node;
	const list = node && listOf(tree, node);
	if (!list) return false;
	list.splice(list.indexOf(node), 1);
	return true;
}

export function insertAfter(tree, node, step) {
	const list = listOf(tree, node) || tree;
	list.splice(list.indexOf(node) + 1, 0, step);
	return step;
}

/** Steps that run before `node`, i.e. the ones whose outputs it may reference. */
export function stepsBefore(tree, node) {
	const earlier = [];
	// A node that isn't in this tree has no earlier steps - never fall back to "all of them",
	// or the target picker would offer outputs that don't exist yet at that point in the run.
	return collectBefore(tree, node, earlier) ? earlier : [];
}

function collectBefore(nodes, target, earlier) {
	for (const node of nodes) {
		if (node === target) return true;
		earlier.push(node);
		if (!isBranching(node)) continue;
		if (collectBefore(node.children.If, target, earlier)) return true;
		if (collectBefore(node.children.Else, target, earlier)) return true;
	}
	return false;
}

function armOf(row) {
	return row.branch === "Else" ? "Else" : "If";
}

function rowIdx(row, index) {
	return row.idx || index + 1;
}
