// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

/**
 * Pure helpers for the advanced filter tree model used by the Vue UI.
 *
 * The serialized shape matches the backend (`frappe/model/filter_tree.py`):
 *
 *   Group: { type: "group", conjunction: "and" | "or", children: [node, ...] }
 *   Rule:  { type: "rule", fieldname, operator, value, doctype? }
 *
 * In the UI every node also carries a transient `id` (used as a stable Vue
 * `:key`) which is stripped on serialization.
 */

let _uid = 0;
function uid() {
	return `fnode-${++_uid}`;
}

export function make_rule({ doctype = null, fieldname = null, operator = "=", value = "" } = {}) {
	return { id: uid(), type: "rule", doctype, fieldname, operator, value };
}

export function make_group(conjunction = "and", children = []) {
	return { id: uid(), type: "group", conjunction, children };
}

/** Build a root AND group from the list view's flat `[doctype, fieldname, operator, value]` filters. */
export function seed_from_filters(filters, doctype) {
	const root = make_group("and");

	(filters || []).forEach(([dt, fieldname, operator, value]) => {
		root.children.push(
			make_rule({
				// Only keep an explicit doctype when it differs from the list's doctype
				// (e.g. a child-table filter), matching the flat 4-element form.
				doctype: dt && dt !== doctype ? dt : null,
				fieldname,
				operator,
				value,
			})
		);
	});

	// Always start with at least one editable rule so the UI is never empty.
	if (!root.children.length) {
		root.children.push(make_rule());
	}

	return root;
}

/** Deep clone a (possibly already-serialized) node, assigning fresh transient ids. */
export function clone_with_ids(node) {
	if (node.type === "group") {
		return make_group(node.conjunction || "and", (node.children || []).map(clone_with_ids));
	}
	return make_rule({
		doctype: node.doctype || null,
		fieldname: node.fieldname || null,
		operator: node.operator || "=",
		value: node.value ?? "",
	});
}

export function is_complete_rule(rule) {
	return !!(rule && rule.type === "rule" && rule.fieldname && rule.operator);
}

/**
 * Serialize a UI node into the backend tree format, dropping incomplete rules
 * (no field chosen) and empty groups. Returns `null` when nothing remains, so an
 * empty builder applies no filter at all.
 */
export function serialize(node) {
	if (node.type === "group") {
		const children = (node.children || []).map(serialize).filter((child) => child !== null);
		if (!children.length) return null;
		return { type: "group", conjunction: node.conjunction || "and", children };
	}

	if (!is_complete_rule(node)) return null;

	const rule = { type: "rule", fieldname: node.fieldname, operator: node.operator, value: node.value };
	if (node.doctype) rule.doctype = node.doctype;
	return rule;
}

/** Count the complete rule leaves in a tree (used for the active-filter indicator). */
export function count_rules(node) {
	if (!node) return 0;
	if (node.type === "group") {
		return (node.children || []).reduce((sum, child) => sum + count_rules(child), 0);
	}
	return is_complete_rule(node) ? 1 : 0;
}
