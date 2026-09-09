// The seeds: a contributed `list.js` above meta's `in_list_view`, and meta's sort above `modified desc`.
import { describe, expect, it } from "vitest";
import type { RawMetaField } from "@framework/ui/FormLayout";

import { DEFAULT_SORT, defaultColumns, defaultSort, fetchFields } from "../defaults";

const FIELDS: RawMetaField[] = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", in_list_view: 1 },
	{ fieldname: "status", label: "Status", fieldtype: "Select", in_list_view: 1 },
	{ fieldname: "amount", label: "Amount", fieldtype: "Currency", in_list_view: 1 },
	{ fieldname: "notes", label: "Notes", fieldtype: "Text" },
];

describe("defaultColumns", () => {
	it("puts the title field first, then every in_list_view field, aligned by fieldtype", () => {
		const columns = defaultColumns({ title_field: "title", fields: FIELDS }, []);
		expect(columns.map((c) => c.fieldname)).toEqual(["title", "status", "amount"]);
		expect(columns.find((c) => c.fieldname === "amount")?.align).toBe("right");
		expect(columns.find((c) => c.fieldname === "title")?.align).toBe("left");
	});

	it("falls back to name and modified when no field is flagged", () => {
		const columns = defaultColumns({ fields: [FIELDS[3]] }, []);
		expect(columns.map((c) => c.fieldname)).toEqual(["name", "modified"]);
	});

	it("takes a contributed list.js's columns over meta, in run order, each fieldname once", () => {
		const columns = defaultColumns({ title_field: "title", fields: FIELDS }, [
			{ columns: [{ fieldname: "status", width: 120 }, { fieldname: "notes" }] },
			{ columns: [{ fieldname: "status" }, { fieldname: "amount" }] },
		]);
		expect(columns.map((c) => c.fieldname)).toEqual(["status", "notes", "amount"]);
		expect(columns[0]).toMatchObject({ label: "Status", width: "120px" });
		expect(columns[1].width).toBeUndefined();
	});

	it("labels a contributed column from meta, or from its fieldname", () => {
		const columns = defaultColumns({ fields: FIELDS }, [
			{ columns: [{ fieldname: "modified" }, { fieldname: "owner" }] },
		]);
		expect(columns.map((c) => c.label)).toEqual(["Last Modified", "owner"]);
	});
});

describe("defaultSort", () => {
	it("reads meta's sort_field and sort_order", () => {
		expect(defaultSort({ sort_field: "amount", sort_order: "ASC" })).toEqual([
			{ fieldname: "amount", direction: "asc" },
		]);
	});

	it("reads a sort_field that already carries its directions", () => {
		expect(defaultSort({ sort_field: "status asc, amount desc" })).toEqual([
			{ fieldname: "status", direction: "asc" },
			{ fieldname: "amount", direction: "desc" },
		]);
	});

	it("falls back to modified desc", () => {
		expect(defaultSort({})).toEqual(DEFAULT_SORT);
		expect(DEFAULT_SORT).toEqual([{ fieldname: "modified", direction: "desc" }]);
	});
});

describe("fetchFields", () => {
	it("asks for name once, then each column", () => {
		expect(
			fetchFields([
				{ fieldname: "status", label: "Status" },
				{ fieldname: "name", label: "Name" },
			])
		).toEqual(["name", "status"]);
	});
});
