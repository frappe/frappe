// The seeds: a contributed `list.js` above meta's `in_list_view`, and meta's sort above `modified desc`.
import { describe, expect, it, vi } from "vitest";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { clearDataCache, feedListRead, readCachedList, takeTicket } from "@framework/ui/cache";

import { DEFAULT_SORT, cellCurrency, contributedRowActions, defaultColumns, defaultSort, fetchFields, cellMark, cellTitle } from "../defaults";

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

	it("falls back to name and modified when only an Image field is flagged", () => {
		const photo: RawMetaField = { fieldname: "photo", label: "Photo", fieldtype: "Image", in_list_view: 1 };
		const columns = defaultColumns({ fields: [photo] }, []);
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

	it("adds each row action's fields after the columns, once", () => {
		const columns = [{ fieldname: "status", label: "Status" }];
		const actions = [
			{ act: "shell.crm.call", fields: ["mobile_no", "status"] },
			{ act: "shell.crm.mail", fields: ["mobile_no", "email_id"] },
		];
		expect(fetchFields(columns, actions)).toEqual(["name", "status", "mobile_no", "email_id"]);
	});

	it("asks for _seen on a Track Seen doctype, and only then", () => {
		const columns = [{ fieldname: "status", label: "Status" }];
		expect(fetchFields(columns, [], { track_seen: 1 })).toEqual(["name", "status", "_seen"]);
		expect(fetchFields(columns, [], { track_seen: 0 })).toEqual(["name", "status"]);
		expect(fetchFields(columns, [], {})).toEqual(["name", "status"]);
	});
});

describe("cell currencies", () => {
	const meta = {
		fields: [
			{ fieldname: "amount", fieldtype: "Currency", options: "currency" },
			{ fieldname: "currency", fieldtype: "Link", options: "Currency" },
			{ fieldname: "fee", fieldtype: "Currency", options: "Company:company:default_currency" },
			{ fieldname: "company", fieldtype: "Link", options: "Company" },
			{ fieldname: "tax", fieldtype: "Currency", options: "parent_currency" },
			{ fieldname: "total", fieldtype: "Currency" },
		],
	};

	it("reads a field the Currency column names straight from the row", () => {
		expect(cellCurrency("amount", meta)).toEqual({ key: "currency", select: "currency" });
	});

	it("reads a linked record's currency through the link, under its own key", () => {
		expect(cellCurrency("fee", meta)).toEqual({
			key: "fee__currency",
			select: "company.default_currency as fee__currency",
		});
	});

	it("has none for a field meta lacks, a field the person cannot read, no options, or another fieldtype", () => {
		expect(cellCurrency("tax", meta)).toBeUndefined();
		expect(cellCurrency("fee", meta, (fieldname) => fieldname !== "company")).toBeUndefined();
		expect(cellCurrency("total", meta)).toBeUndefined();
		expect(cellCurrency("currency", meta)).toBeUndefined();
	});

	it("asks for each currency beside the columns", () => {
		const columns = ["amount", "fee", "tax"].map((fieldname) => ({ fieldname, label: fieldname }));
		expect(fetchFields(columns, [], meta)).toEqual([
			"name",
			"amount",
			"fee",
			"tax",
			"currency",
			"company.default_currency as fee__currency",
		]);
	});
});

describe("fetchFields and the shared cache", () => {
	it("gives a query the cache keeps, whatever shape a column adds", () => {
		const meta = {
			fields: [
				{ fieldname: "customer", fieldtype: "Link", options: "Customer", link_title: "customer_name", link_mark: { kind: "image" as const, field: "image" } },
				{ fieldname: "company", fieldtype: "Link", options: "Company" },
				{ fieldname: "fee", fieldtype: "Currency", options: "Company:company:default_currency" },
			],
			image_field: "photo",
		};
		const columns = ["customer", "company", "fee"].map((fieldname) => ({ fieldname, label: fieldname }));
		const fields = fetchFields(columns, [], meta);
		expect(fields.length).toBeGreaterThan(columns.length + 3);
		clearDataCache();
		feedListRead(takeTicket(), "Order", { fields }, { data: [{ name: "A", modified: "2026-11-01" }], has_next_page: false });
		expect(readCachedList("Order", { fields })).toBeDefined();
	});
});

describe("contributedRowActions", () => {
	it("joins every app's row actions in run order and lists an act named twice once", () => {
		const call = { act: "shell.crm.call", fields: ["mobile_no"] };
		const mail = { act: "shell.crm.mail", fields: ["email_id"] };
		const again = { act: "shell.crm.call", fields: ["phone"] };
		expect(contributedRowActions([{ rowActions: [call] }, {}, { rowActions: [mail, again] }])).toEqual([
			call,
			mail,
		]);
	});

	it("runs a foreign app's row action after the owner's, whatever the site's app order", async () => {
		vi.resetModules();
		vi.doMock("virtual:frappe/contributions", () => ({
			default: {
				doctypes: [
					{ kind: "customList", app: "helpdesk", doctype: "CRM Lead", handlers: { rowActions: [{ act: "shell.hd.ticket", fields: ["email"] }] } },
					{ kind: "list", app: "crm", doctype: "CRM Lead", handlers: { rowActions: [{ act: "shell.crm.call", fields: ["mobile_no"] }] } },
				],
				pages: [], itemTypes: [], replacements: [], settings: [], acts: [],
			},
		}));
		vi.doMock("@/recordPage", () => ({ addFileScript: vi.fn(), addPageFile: vi.fn() }));
		const { listHandlersFor, registerContributions } = await import("@/contributions/registry");
		registerContributions(["frappe", "helpdesk", "crm"]);

		vi.doUnmock("virtual:frappe/contributions");
		vi.doUnmock("@/recordPage");
		const contributed = listHandlersFor("CRM Lead");
		expect(contributed.map(({ app }) => app)).toEqual(["crm", "helpdesk"]);
		expect(contributedRowActions(contributed.map(({ handlers }) => handlers)).map((one) => one.act)).toEqual([
			"shell.crm.call",
			"shell.hd.ticket",
		]);
	});

	it("refuses an act on the list surface, which would ask itself whether it is available", () => {
		const own = { act: "list.create", fields: [] };
		expect(contributedRowActions([{ rowActions: [own] }])).toEqual([]);
	});
});

describe("cell marks", () => {
	const meta = {
		title_field: "lead_name",
		image_field: "image",
		fields: [
			{ fieldname: "status", fieldtype: "Link", link_mark: { kind: "color" as const, field: "color" } },
			{ fieldname: "lead_name", fieldtype: "Data" },
		],
	};
	const columns = [
		{ fieldname: "lead_name", label: "Name" },
		{ fieldname: "status", label: "Status" },
	];

	it("reads a Link column's mark through the link, under its own key", () => {
		expect(cellMark("status", meta)).toEqual({
			source: { kind: "color", field: "color" },
			key: "status__mark",
			select: "status.color as status__mark",
		});
	});

	it("shows the title column's own image_field", () => {
		expect(cellMark("lead_name", meta)?.source).toEqual({ kind: "image", field: "image" });
		expect(cellMark("lead_name", meta)?.key).toBe("image");
	});

	it("marks no other column", () => {
		expect(cellMark("modified", meta)).toBeUndefined();
	});

	it("asks for each mark beside the columns", () => {
		expect(fetchFields(columns, [], meta)).toEqual([
			"name",
			"lead_name",
			"status",
			"image",
			"status.color as status__mark",
		]);
	});
});

describe("cell titles", () => {
	const meta = {
		fields: [
			{ fieldname: "deal", fieldtype: "Link", options: "CRM Deal", link_title: "organization" },
			{ fieldname: "owner_user", fieldtype: "Link", options: "User" },
			{ fieldname: "reference", fieldtype: "Dynamic Link", options: "reference_doctype", link_title: "title" },
		],
	};

	it("reads a Link column's target title through the link, under its own key", () => {
		expect(cellTitle("deal", meta)).toEqual({ key: "deal__title", select: "deal.organization as deal__title" });
	});

	it("has none for a Link whose target shows no title, a Dynamic Link, or a field meta lacks", () => {
		expect(cellTitle("owner_user", meta)).toBeUndefined();
		expect(cellTitle("reference", meta)).toBeUndefined();
		expect(cellTitle("gone", meta)).toBeUndefined();
	});

	it("asks for each title beside the columns", () => {
		const columns = ["deal", "owner_user"].map((fieldname) => ({ fieldname, label: fieldname }));
		expect(fetchFields(columns, [], meta)).toEqual([
			"name",
			"deal",
			"owner_user",
			"deal.organization as deal__title",
		]);
	});
});
