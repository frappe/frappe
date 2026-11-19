// The stored shape as claims: what a row's JSON becomes on the page, and what the page stores.
import { describe, expect, it } from "vitest";
import {
	columnsFrom,
	filtersFrom,
	quickFilterFieldsFrom,
	sortFrom,
	toStoredColumns,
	toStoredQuickFilterFields,
} from "../storedSettings";

const FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data" },
	{ fieldname: "amount", label: "Amount", fieldtype: "Currency" },
	{ fieldname: "secret", label: "Secret", fieldtype: "Data", permlevel: 1 },
	{ fieldname: "notes_section", label: "Notes", fieldtype: "Section Break" },
];

const readable = (fieldname: string) => fieldname !== "secret";

describe("columnsFrom", () => {
	it("names each column from meta and keeps a stored width", () => {
		const columns = columnsFrom([{ fieldname: "amount", width: "120px" }, { fieldname: "title" }], FIELDS, readable);
		expect(columns).toEqual([
			{ fieldname: "amount", label: "Amount", align: "right", width: "120px" },
			{ fieldname: "title", label: "Title", align: "left" },
		]);
	});

	it("keeps a standard field and drops what meta lacks, the person cannot read, a break, and a repeat", () => {
		const stored = [
			{ fieldname: "modified" },
			{ fieldname: "gone" },
			{ fieldname: "secret" },
			{ fieldname: "notes_section" },
			{ fieldname: "title" },
			{ fieldname: "title" },
		];
		expect(columnsFrom(stored, FIELDS, readable).map((c) => c.fieldname)).toEqual(["modified", "title"]);
	});

	it("drops a stored Image or Attachment Gallery column", () => {
		const fields = [
			...FIELDS,
			{ fieldname: "photo", label: "Photo", fieldtype: "Image" },
			{ fieldname: "gallery", label: "Gallery", fieldtype: "Attachment Gallery" },
		];
		const stored = [{ fieldname: "photo" }, { fieldname: "gallery" }, { fieldname: "title" }];
		expect(columnsFrom(stored, fields, readable).map((c) => c.fieldname)).toEqual(["title"]);
	});

	it("reads a shape that is not a list of columns as nothing", () => {
		expect(columnsFrom("title", FIELDS, readable)).toEqual([]);
		expect(columnsFrom([{ width: "1px" }, null, 3], FIELDS, readable)).toEqual([]);
	});
});

describe("sortFrom", () => {
	it("keeps a sortable field with a direction and drops the rest", () => {
		const stored = [
			{ fieldname: "amount", direction: "desc" },
			{ fieldname: "secret", direction: "asc" },
			{ fieldname: "title", direction: "up" },
			{ fieldname: "creation", direction: "asc" },
		];
		expect(sortFrom(stored, FIELDS, readable)).toEqual([
			{ fieldname: "amount", direction: "desc" },
			{ fieldname: "creation", direction: "asc" },
		]);
	});
});

describe("quickFilterFieldsFrom", () => {
	it("resolves fieldnames to the filterable fields, in the stored order", () => {
		const fields = quickFilterFieldsFrom(["amount", "name", "secret", "gone", "amount"], "Lead", FIELDS, readable);
		expect(fields.map((field) => field.fieldname)).toEqual(["amount", "name"]);
		expect(fields[1]).toMatchObject({ fieldtype: "Link", options: "Lead" });
	});
});

describe("filtersFrom", () => {
	it("reads wire triples of the fields the person may filter, and drops the rest", () => {
		const stored = [["title", "=", "Acme"], ["secret", "=", "x"], ["gone", "=", "x"], "title", ["amount", ">", 5]];
		const filters = filtersFrom(stored, "Lead", FIELDS, readable);
		expect(filters).toMatchObject([
			{ fieldname: "title", operator: "equals", value: "Acme" },
			{ fieldname: "amount", operator: ">", value: 5 },
		]);
	});

	it("drops a condition whose operator the filter UI lacks, or that has no operator", () => {
		const stored = [["title", "like", "%x%"], ["title", "Between", [1, 2]], ["title"], ["amount", ">", 5]];
		expect(filtersFrom(stored, "Lead", FIELDS, readable)).toMatchObject([{ fieldname: "amount", operator: ">" }]);
	});

	it("reads a shape that is not a list as nothing", () => {
		expect(filtersFrom({ title: "Acme" }, "Lead", FIELDS, readable)).toEqual([]);
		expect(filtersFrom(undefined, "Lead", FIELDS, readable)).toEqual([]);
	});
});

describe("the stored form", () => {
	it("keeps fieldname and width and drops the label", () => {
		expect(toStoredColumns([{ fieldname: "title", label: "Mine", width: "90px" }, { fieldname: "amount", label: "Amount" }])).toEqual([
			{ fieldname: "title", width: "90px" },
			{ fieldname: "amount" },
		]);
		expect(toStoredQuickFilterFields([{ fieldname: "title", value: "title", label: "Title", fieldtype: "Data" }])).toEqual(["title"]);
	});
});
