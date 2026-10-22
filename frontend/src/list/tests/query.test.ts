// The URL encoding: an equals filter bare, any other operator as a pair, the sort under `_sort`.
import { describe, expect, it } from "vitest";
import type { FilterCondition } from "@framework/ui/Filter";

import { addressFromQuery, createValues, ownedKeys, queryFromAddress, sameQuery } from "../query";

const FIELDS = [
	{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nClosed" },
	{ fieldname: "company", label: "Company", fieldtype: "Link", options: "Company" },
	{ fieldname: "is_active", label: "Active", fieldtype: "Check" },
	{ fieldname: "amount", label: "Amount", fieldtype: "Currency" },
];

function condition(fieldname: string, operator: string, value: unknown): FilterCondition {
	return { fieldname, operator, value } as FilterCondition;
}

describe("queryFromAddress", () => {
	it("writes an equals filter bare and any other operator as a pair", () => {
		const query = queryFromAddress({
			filters: [condition("status", "equals", "Open"), condition("amount", ">", "100")],
			sort: [],
		});
		expect(query).toEqual({ status: "Open", amount: JSON.stringify([">", "100"]) });
	});

	it("writes a Check as 1 or 0 and a like as its wire form", () => {
		const query = queryFromAddress({
			filters: [condition("is_active", "equals", "Yes"), condition("company", "like", "Acme")],
			sort: [],
		});
		expect(query.is_active).toBe("1");
		expect(query.company).toBe(JSON.stringify(["LIKE", "%Acme%"]));
	});

	it("writes the sort as an order_by string and drops a condition with no value", () => {
		const query = queryFromAddress({
			filters: [condition("status", "equals", ""), condition("company", "in", [])],
			sort: [
				{ fieldname: "amount", direction: "desc" },
				{ fieldname: "status", direction: "asc" },
			],
		});
		expect(query).toEqual({ _sort: "amount desc, status asc" });
	});
});

describe("addressFromQuery", () => {
	it("reads a bare value as equals, a pair as its operator, and a like as bare text", () => {
		const address = addressFromQuery(
			{ status: "Open", amount: JSON.stringify([">", "100"]), company: '["LIKE","%Acme%"]' },
			"Lead",
			FIELDS
		);
		expect(address.filters?.map((c) => [c.fieldname, c.operator, c.value])).toEqual([
			["status", "equals", "Open"],
			["amount", ">", "100"],
			["company", "like", "Acme"],
		]);
	});

	it("reads a Check from 1 or 0 as Yes or No", () => {
		const address = addressFromQuery({ is_active: "1" }, "Lead", FIELDS);
		expect(address.filters?.[0]).toMatchObject({ operator: "equals", value: "Yes" });
	});

	it("reads the sort and ignores a key that names no field", () => {
		const address = addressFromQuery({ _sort: "amount desc", view: "kanban" }, "Lead", FIELDS);
		expect(address.sort).toEqual([{ fieldname: "amount", direction: "desc" }]);
		expect(address.filters).toBeUndefined();
	});

	it("round-trips what it wrote", () => {
		const written = queryFromAddress({
			filters: [condition("status", "not equals", "Closed"), condition("is_active", "equals", "No")],
			sort: [{ fieldname: "status", direction: "asc" }],
		});
		const read = addressFromQuery(written, "Lead", FIELDS);
		expect(queryFromAddress({ filters: read.filters!, sort: read.sort! })).toEqual(written);
	});
});

describe("ownedKeys and sameQuery", () => {
	it("owns the sort key and every filterable field, and nothing else", () => {
		const owned = ownedKeys("Lead", FIELDS);
		expect(owned.has("_sort")).toBe(true);
		expect(owned.has("status")).toBe(true);
		expect(owned.has("view")).toBe(false);
	});

	it("compares queries by content, in any key order", () => {
		expect(sameQuery({ a: "1", b: "2" }, { b: "2", a: "1" })).toBe(true);
		expect(sameQuery({ a: "1" }, { a: "2" })).toBe(false);
	});
});

describe("createValues", () => {
	const WITH_TABLE = [
		...FIELDS,
		{ fieldname: "title", label: "Title", fieldtype: "Data" },
		{ fieldname: "items", label: "Items", fieldtype: "Table", options: "Lead Item" },
		{ fieldname: "tags", label: "Tags", fieldtype: "Table MultiSelect", options: "Lead Tag" },
	];

	it("takes the equals filters and leaves every other operator out", () => {
		const values = createValues(
			[
				condition("status", "equals", "Open"),
				condition("company", "equals", "Acme"),
				condition("amount", ">", "100"),
				condition("title", "like", "Big"),
				condition("status", "not equals", "Closed"),
			],
			WITH_TABLE
		);
		expect(values).toEqual({ status: "Open", company: "Acme" });
	});

	it("turns a Check filter into 1 or 0", () => {
		expect(createValues([condition("is_active", "equals", "Yes")], WITH_TABLE)).toEqual({ is_active: 1 });
		expect(createValues([condition("is_active", "equals", "No")], WITH_TABLE)).toEqual({ is_active: 0 });
	});

	it("leaves out a filter on a field the doctype does not own, or on a table field", () => {
		const values = createValues(
			[
				condition("owner", "equals", "ann@example.com"),
				condition("items", "equals", "ITEM-1"),
				condition("tags", "equals", "urgent"),
				condition("status", "equals", "Open"),
			],
			WITH_TABLE
		);
		expect(values).toEqual({ status: "Open" });
	});

	it("leaves out a condition with no value yet", () => {
		expect(createValues([condition("status", "equals", ""), condition("company", "equals", null)], WITH_TABLE)).toEqual({});
	});

	it("keeps a Yes or No typed into a field that is not a Check as the text", () => {
		const fields = [{ fieldname: "answer", label: "Answer", fieldtype: "Select", options: "Yes\nNo" }];
		expect(createValues([condition("answer", "equals", "Yes")], fields)).toEqual({ answer: "Yes" });
	});
});
