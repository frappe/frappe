// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE
//
// Unit tests for the pure advanced-filter tree model. These have no Frappe or DOM
// dependency and can be run under vitest (`vitest run`) or the lightweight runner
// in this folder. They mirror the backend converter's expectations so the
// serialized shape stays in lock-step with frappe/model/filter_tree.py.

import { describe, expect, it } from "vitest";

import {
	clone_with_ids,
	count_rules,
	is_complete_rule,
	make_group,
	make_rule,
	seed_from_filters,
	serialize,
} from "./tree.js";

describe("advanced filter tree model", () => {
	it("creates rules and groups with stable, unique ids", () => {
		const a = make_rule();
		const b = make_rule();
		const g = make_group("or");
		expect(a.id).not.toEqual(b.id);
		expect(a.type).toBe("rule");
		expect(g.type).toBe("group");
		expect(g.conjunction).toBe("or");
		expect(g.children).toEqual([]);
	});

	it("seeds a root AND group from flat filters", () => {
		const root = seed_from_filters(
			[
				["ToDo", "status", "=", "Open"],
				["ToDo", "priority", "=", "High"],
			],
			"ToDo"
		);
		expect(root.type).toBe("group");
		expect(root.conjunction).toBe("and");
		expect(root.children).toHaveLength(2);
		// Base-doctype filters drop the explicit doctype.
		expect(root.children[0]).toMatchObject({ doctype: null, fieldname: "status", operator: "=" });
	});

	it("keeps an explicit doctype for child-table filters when seeding", () => {
		const root = seed_from_filters([["Sales Order Item", "qty", ">", 5]], "Sales Order");
		expect(root.children[0].doctype).toBe("Sales Order Item");
	});

	it("seeds an empty editable rule when there are no filters", () => {
		const root = seed_from_filters([], "ToDo");
		expect(root.children).toHaveLength(1);
		expect(is_complete_rule(root.children[0])).toBe(false);
	});

	it("serializes a flat group, stripping ids and the null doctype", () => {
		const root = make_group("and", [
			make_rule({ fieldname: "status", operator: "=", value: "Open" }),
			make_rule({ fieldname: "priority", operator: "=", value: "High" }),
		]);
		expect(serialize(root)).toEqual({
			type: "group",
			conjunction: "and",
			children: [
				{ type: "rule", fieldname: "status", operator: "=", value: "Open" },
				{ type: "rule", fieldname: "priority", operator: "=", value: "High" },
			],
		});
	});

	it("serializes nested groups", () => {
		const root = make_group("or", [
			make_group("and", [
				make_rule({ fieldname: "a", operator: "=", value: 1 }),
				make_rule({ fieldname: "b", operator: "=", value: 2 }),
			]),
			make_rule({ fieldname: "c", operator: "=", value: 3 }),
		]);
		expect(serialize(root)).toEqual({
			type: "group",
			conjunction: "or",
			children: [
				{
					type: "group",
					conjunction: "and",
					children: [
						{ type: "rule", fieldname: "a", operator: "=", value: 1 },
						{ type: "rule", fieldname: "b", operator: "=", value: 2 },
					],
				},
				{ type: "rule", fieldname: "c", operator: "=", value: 3 },
			],
		});
	});

	it("drops incomplete rules and empty groups on serialize", () => {
		const root = make_group("and", [
			make_rule({ fieldname: "status", operator: "=", value: "Open" }),
			make_rule(), // incomplete, no fieldname -> dropped
			make_group("or", []), // empty group -> dropped
		]);
		expect(serialize(root)).toEqual({
			type: "group",
			conjunction: "and",
			children: [{ type: "rule", fieldname: "status", operator: "=", value: "Open" }],
		});
	});

	it("serializes to null when nothing is complete", () => {
		expect(serialize(make_group("and", [make_rule(), make_group("or", [])]))).toBeNull();
	});

	it("preserves an explicit doctype on serialize", () => {
		const root = make_group("and", [
			make_rule({ doctype: "Sales Order Item", fieldname: "qty", operator: ">", value: 5 }),
		]);
		expect(serialize(root).children[0]).toEqual({
			type: "rule",
			doctype: "Sales Order Item",
			fieldname: "qty",
			operator: ">",
			value: 5,
		});
	});

	it("round-trips through clone_with_ids (re-keyed, same serialized shape)", () => {
		const tree = {
			type: "group",
			conjunction: "or",
			children: [
				{
					type: "group",
					conjunction: "and",
					children: [{ type: "rule", fieldname: "a", operator: "=", value: 1 }],
				},
				{ type: "rule", fieldname: "b", operator: "in", value: ["x", "y"] },
			],
		};
		const cloned = clone_with_ids(tree);
		expect(cloned.id).toBeTruthy();
		expect(cloned.children[0].id).not.toEqual(cloned.children[1].id);
		expect(serialize(cloned)).toEqual(tree);
	});

	it("counts only complete rule leaves", () => {
		const root = make_group("or", [
			make_rule({ fieldname: "a", operator: "=", value: 1 }),
			make_group("and", [
				make_rule({ fieldname: "b", operator: "=", value: 2 }),
				make_rule(), // incomplete
			]),
		]);
		expect(count_rules(root)).toBe(2);
	});
});
