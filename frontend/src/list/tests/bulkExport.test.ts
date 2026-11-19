import { describe, expect, it } from "vitest";
import { exportFilters } from "../bulkExport";

describe("exportFilters", () => {
	it("exports the named records by name", () => {
		expect(exportFilters({ names: ["A", "B"] })).toEqual({ name: ["in", ["A", "B"]] });
	});

	it("exports every record the filters show", () => {
		expect(exportFilters({ filters: { status: ["=", "Open"] } })).toEqual({ status: ["=", "Open"] });
	});

	it("takes empty or_filters as none", () => {
		expect(exportFilters({ filters: {}, or_filters: [] })).toEqual({});
		expect(exportFilters({ filters: {}, or_filters: {} })).toEqual({});
	});

	it("cannot export a scope with or_filters", () => {
		expect(exportFilters({ filters: {}, or_filters: [["status", "=", "Open"]] })).toBeNull();
		expect(exportFilters({ filters: {}, or_filters: { status: "Open" } })).toBeNull();
	});
});
