import { describe, expect, it, vi } from "vitest";
import { getTranslations } from "@framework/ui/api";
import { loadTranslations } from "@/i18n";
import type { ConditionField } from "@framework/ui/ConditionBuilder";
import { LinkFilters, targetChange } from "../linkFilters";
import { RuleWords } from "../ruleWords";

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	getTranslations: vi.fn().mockResolvedValue({ data: {} }),
}));

const CUSTOMER: ConditionField[] = [
	{ label: "Disabled", value: "disabled", fieldname: "disabled", fieldtype: "Check" },
	{ label: "Company", value: "company", fieldname: "company", fieldtype: "Link", options: "Company" },
	{ label: "Customer Name", value: "customer_name", fieldname: "customer_name", fieldtype: "Data" },
	{ label: "Credit Days", value: "credit_days", fieldname: "credit_days", fieldtype: "Int" },
];
const record = new RuleWords([
	{ fieldname: "company", label: "Billing Company", fieldtype: "Link", options: "Company" },
	{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
]);
const filters = new LinkFilters("Customer", CUSTOMER, record);

describe("a Link field's filters", () => {
	it("reads the stored list as a flat AND tree and writes the same list back", () => {
		const raw = JSON.stringify([
			["Customer", "disabled", "=", 0],
			["Customer", "company", "=", "eval:doc.company"],
			["Customer", "customer_name", "like", "%Corp%"],
			["Customer", "credit_days", ">", 30],
		]);
		const tree = filters.read(raw);
		expect(tree).toEqual({
			conjunction: "and",
			conditions: [
				{ fieldname: "disabled", operator: "equals", value: "No" },
				{ fieldname: "company", operator: "equals", value: "eval:doc.company" },
				{ fieldname: "customer_name", operator: "like", value: "Corp" },
				{ fieldname: "credit_days", operator: ">", value: "30" },
			],
		});
		expect(filters.write(tree!)).toBe(raw);
	});

	it("says each filter in words, a field of this record as this record's", () => {
		const raw = JSON.stringify([
			["Customer", "disabled", "=", 0],
			["Customer", "company", "=", "eval:doc.company"],
		]);
		expect(filters.say(raw)).toEqual({
			kind: "rules",
			text: "Disabled is off and Company is this record's Billing Company",
		});
		expect(filters.sentence(raw)).toBe("Filters: Disabled is off and Company is this record's Billing Company");
		expect(filters.say("")).toEqual({ kind: "empty", text: "All customers" });
		expect(filters.write({ conjunction: "and", conditions: [] })).toBe("");
	});

	it("keeps as code a list the builder cannot show: bad JSON, another DocType, an unknown field", () => {
		for (const raw of [
			"[[",
			JSON.stringify([["Supplier", "disabled", "=", 0]]),
			JSON.stringify([["Customer", "territory", "=", "India"]]),
			JSON.stringify({ disabled: 0 }),
			JSON.stringify([["Customer", "customer_name", "like", "Corp%"]]),
			JSON.stringify([["Customer", "customer_name", "like", "C%rp"]]),
			JSON.stringify([["Customer", "disabled", "=", "eval:doc.flag"]]),
		]) {
			expect(filters.read(raw)).toBeNull();
			expect(filters.say(raw)).toEqual({ kind: "code", text: raw });
		}
	});

	it("keeps as code a filter with no value, which writing the tree would drop", () => {
		for (const raw of [
			JSON.stringify([["Customer", "company", "=", ""]]),
			JSON.stringify([["Customer", "company", "=", null]]),
			JSON.stringify([["Customer", "company", "in", []]]),
			JSON.stringify([["Customer", "customer_name", "like", "%%"]]),
		]) {
			expect(filters.read(raw)).toBeNull();
		}
	});

	it("drops the filters when the Link points at another DocType", () => {
		const link = { fieldname: "customer", fieldtype: "Link", options: "Customer", link_filters: "[]" };
		expect(targetChange(link, "Supplier")).toEqual({ options: "Supplier", link_filters: "" });
		expect(targetChange({ ...link, link_filters: undefined }, "Supplier")).toEqual({ options: "Supplier" });
	});

	it("writes \"is not\" as \"is\" with the other value, the only form the query engines take", () => {
		const tree = {
			conjunction: "and" as const,
			conditions: [
				{ fieldname: "company", operator: "is not" as const, value: "set" },
				{ fieldname: "customer_name", operator: "is not" as const, value: "not set" },
			],
		};
		const raw = filters.write(tree);
		expect(JSON.parse(raw)).toEqual([
			["Customer", "company", "is", "not set"],
			["Customer", "customer_name", "is", "set"],
		]);
		expect(filters.read(JSON.stringify([["Customer", "company", "is not", "set"]]))).toBeNull();
	});

	it("names a field with two filters, since a Link search keeps one filter per field", () => {
		const twice = (second: string) => ({
			conjunction: "and" as const,
			conditions: [
				{ fieldname: "credit_days", operator: ">" as const, value: "30" },
				{ fieldname: "credit_days", operator: "<" as const, value: second },
			],
		});
		expect(filters.problem(twice("60"))).toBe(
			"Credit Days has two filters, and a Link search keeps only one. Use one filter, such as Between."
		);
		expect(filters.problem(twice(""))).toBe("");
	});

	it("shows the code one row per line without touching a comma inside a value", () => {
		const raw = JSON.stringify([["Customer", "customer_name", "=", "Acme,Inc"]]);
		expect(filters.code(raw)).toBe('[\n  ["Customer", "customer_name", "=", "Acme,Inc"]\n]');
		expect(filters.fromCode(filters.code(raw))).toBe(raw);
	});
});

describe("the all-records summary", () => {
	it("keeps a translated name as translated", async () => {
		vi.mocked(getTranslations).mockResolvedValue({ data: { Customer: "Kunde", "All {0}": "Alle {0}" } });
		await loadTranslations("v1", "de");
		try {
			expect(filters.say("").text).toBe("Alle Kunde");
		} finally {
			vi.mocked(getTranslations).mockResolvedValue({ data: {} });
			await loadTranslations("v2", "en");
		}
	});
});
