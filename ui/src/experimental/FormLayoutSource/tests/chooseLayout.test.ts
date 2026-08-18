import { describe, expect, it } from "vitest";
import { chooseLayout, matchesCondition } from "../chooseLayout";
import type { FormLayoutRow, LayoutTree } from "../types";

function tree(name: string): LayoutTree {
	return [{ name, sections: [] }];
}

function row(name: string, condition?: string): FormLayoutRow {
	return { name, condition, layout: tree(name) };
}

describe("matchesCondition", () => {
	it("evaluates a JS expression over the doc", () => {
		const doc = { lead_type: "Enterprise" };
		expect(matchesCondition("doc.lead_type == 'Enterprise'", doc)).toBe(true);
		expect(matchesCondition("doc.lead_type == 'SMB'", doc)).toBe(false);
	});

	it("accepts the eval: prefix", () => {
		expect(matchesCondition("eval:doc.status == 'Open'", { status: "Open" })).toBe(
			true
		);
	});

	it("reads a bare fieldname for truthiness, arrays for non-emptiness", () => {
		expect(matchesCondition("email", { email: "a@b.c" })).toBe(true);
		expect(matchesCondition("email", { email: "" })).toBe(false);
		expect(matchesCondition("tags", { tags: [] })).toBe(false);
		expect(matchesCondition("tags", { tags: ["x"] })).toBe(true);
	});

	it("matches nothing when the expression throws or is blank", () => {
		expect(matchesCondition("doc.a.b.c == 1", {})).toBe(false);
		expect(matchesCondition("eval:", { x: 1 })).toBe(false);
	});
});

describe("chooseLayout", () => {
	const doc = { status: "Open" };

	it("picks the first matching conditional row", () => {
		const rows = [
			row("default"),
			row("open", "doc.status == 'Open'"),
			row("also-open", "doc.status == 'Open'"),
		];
		expect(chooseLayout(rows, doc)).toEqual(tree("open"));
	});

	it("falls back to the default row when no condition matches", () => {
		const rows = [row("closed", "doc.status == 'Closed'"), row("default")];
		expect(chooseLayout(rows, doc)).toEqual(tree("default"));
	});

	it("returns null with no rows or no default", () => {
		expect(chooseLayout([], doc)).toBeNull();
		expect(chooseLayout([row("closed", "doc.status == 'Closed'")], doc)).toBeNull();
	});

	it("re-picks as the doc changes", () => {
		const rows = [row("default"), row("vip", "doc.tier == 'VIP'")];
		expect(chooseLayout(rows, { tier: "" })).toEqual(tree("default"));
		expect(chooseLayout(rows, { tier: "VIP" })).toEqual(tree("vip"));
	});
});
