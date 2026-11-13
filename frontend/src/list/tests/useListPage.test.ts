// The composable as claims: what seeds it, what it writes to the URL, when it rebuilds the list,
// and what a delete does. The api wrapper is faked and feeds the real cache; the router and
// history are real.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick, watch, type App } from "vue";
import { createRouter, createWebHistory, type Router } from "vue-router";

const fake = vi.hoisted(() => ({
	meta: null as Record<string, unknown> | null,
	lists: [] as any[],
	tiers: { site: null, user: null } as { app?: unknown; site: unknown; user: unknown },
	listDocuments: vi.fn(),
	countDocuments: vi.fn(),
	deleteDocument: vi.fn(),
	bulkDelete: vi.fn(),
	runMethod: vi.fn(),
	columnItems: null as { name: string; fields?: string[] }[] | null,
}));

vi.mock("@framework/ui/api", async (original) => ({
	isApiError: (await original<typeof import("@framework/ui/api")>()).isApiError,
	isBulkQueued: (await original<typeof import("@framework/ui/api")>()).isBulkQueued,
	bulkDeleteDocuments: fake.bulkDelete,
	getMeta: vi.fn(async () => ({ data: fake.meta, children: [] })),
	listDocuments: fake.listDocuments,
	countDocuments: fake.countDocuments,
	deleteDocument: fake.deleteDocument,
	runMethod: fake.runMethod,
}));

import { filtersFit } from "../useListView";
import { createListPageLists } from "@/listPage/createListPage";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import {
	markDoctypeMetaStale,
	resetDoctypeMeta,
	useDoctypeMeta,
} from "@framework/ui/useDoctypeMeta";
import { setSession } from "@framework/ui/useSession";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import type { Session } from "@framework/ui/api";
import { clearDataCache, feedListRead, settleTicket, takeTicket } from "@framework/ui/cache";
import { readListMemory, recallRows, rememberRows, writeListMemory } from "../pageState";
import type { SavedView } from "../savedView";
import { useListPage } from "../useListPage";
import { useListView } from "../useListView";
import { markListSettingsStale, resetListSettings, useListSettings } from "../useListSettings";

const SETTINGS_API = "frappe.desk.doctype.doctype_view.api";

const FIELDS = [
	{ fieldname: "title", label: "Title", fieldtype: "Data", in_list_view: 1 },
	{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nClosed", in_list_view: 1 },
	{ fieldname: "amount", label: "Amount", fieldtype: "Currency", in_list_view: 1 },
];

const addresses = new Addresses({ doctypes: { Lead: ["lead", "crm"] }, modules: { crm: "CRM" } });
const boot = { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm", modular: false } } };

let router: Router;
let app: App | null = null;
let page: ReturnType<typeof composed>;
// The view the page opens, when a test opens one; else the plain List view.
let opened: SavedView | undefined;

/** One list read, answered when a test assigns `data`; `count` is 42 unless a test says otherwise. */
function fakeList(doctype: string, query: Record<string, unknown>, options?: { include?: string[] }) {
	let resolve!: (answer: unknown) => void;
	const promise = new Promise((done) => (resolve = done));
	const ticket = takeTicket();
	const list = {
		query,
		include: options?.include,
		hasNextPage: true,
		count: 42 as number | null,
		capped: false,
		set data(rows: Record<string, unknown>[]) {
			const answer = { data: rows, has_next_page: list.hasNextPage, count: list.count, count_capped: list.capped };
			feedListRead(ticket, doctype, query, answer as never);
			settleTicket(ticket);
			resolve(answer);
		},
	};
	fake.lists.push(list);
	return promise;
}

function rowsNamed(count: number, from = 0) {
	return Array.from({ length: count }, (_, index) => ({ name: `LEAD-${from + index}` }));
}

async function mount(path: string) {
	router = createRouter({
		history: createWebHistory("/"),
		routes: [
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/:name", name: "record", component: { render: () => null } },
		],
	});
	registerShell({ boot: boot as unknown as Boot, addresses, router });
	await router.replace(path);
	const root = document.createElement("div");
	document.body.appendChild(root);
	app = createApp(
		defineComponent({
			setup() {
				page = composed();
				return () => null;
			},
		})
	);
	app.use(router);
	app.mount(root);
	await settle();
}

/** The page state and the List renderer's, read as one object as the page and renderer see them. */
function composed() {
	const listPage = useListPage("Lead", opened);
	const { filters, sort, seeded } = listPage.view;
	const lists = createListPageLists();
	if (fake.columnItems) vi.spyOn(lists.columns, "visible").mockReturnValue(fake.columnItems);
	return { ...listPage, ...useListView(listPage.view, lists), filters, sort, seeded };
}

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** A settings call answers the tiers, a write patched in. */
function answer(method: string, args: Record<string, any>) {
	if (method.endsWith(".save")) {
		const row = (fake.tiers[args.scope as "site" | "user"] ?? {}) as Record<string, unknown>;
		fake.tiers = { ...fake.tiers, [args.scope]: { ...row, ...args.settings } };
	}
	if (method.endsWith(".reset")) {
		const row = { ...(fake.tiers[args.scope as "site" | "user"] as Record<string, unknown>) };
		delete row[args.key];
		fake.tiers = { ...fake.tiers, [args.scope]: Object.keys(row).length ? row : null };
	}
	return Promise.resolve({ data: fake.tiers });
}

function writes() {
	return fake.runMethod.mock.calls.filter(([method]) => method.startsWith(SETTINGS_API) && !method.endsWith(".get"));
}

/** A changed query waits out the typing debounce before it builds a list. */
async function settleQuery() {
	await new Promise((resolve) => setTimeout(resolve, 350));
	await settle();
}

const SESSION: Session = {
	user: { name: "alice@example.com", full_name: "Alice", email: "alice@example.com", user_image: null, document_follow_notify: false },
	roles: ["Desk User"],
	lang: "en",
	timezone: "Asia/Kolkata",
	defaults: {},
};

beforeEach(() => {
	fake.columnItems = null;
	resetDoctypeMeta();
	resetUserRoles();
	setSession(SESSION);
	resetListSettings();
	// A rows key is never empty, so this clears the last test's memory.
	rememberRows("Lead", { query: "", pageSize: 20 });
	clearDataCache();
	history.replaceState(null, "");
	fake.meta = { name: "Lead", title_field: "title", sort_field: "amount", sort_order: "ASC", fields: FIELDS };
	opened = undefined;
	fake.lists = [];
	fake.tiers = { site: null, user: null };
	fake.listDocuments.mockReset().mockImplementation(fakeList);
	fake.runMethod.mockReset().mockImplementation(answer);
	fake.countDocuments.mockReset().mockResolvedValue({ data: 1234 });
	fake.deleteDocument.mockReset().mockResolvedValue({ data: "ok" });
	fake.bulkDelete.mockReset().mockResolvedValue({ data: { total: 0, done: [], failed: [] } });
});

afterEach(() => {
	app?.unmount();
	app = null;
	document.body.innerHTML = "";
});

describe("seeding", () => {
	it("takes columns and sort from meta and reads the query it was opened with", async () => {
		await mount("/lead?status=Open&_sort=title%20desc&view=kanban");
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["title", "status", "amount"]);
		expect(page.filters.value).toHaveLength(1);
		expect(page.filters.value[0]).toMatchObject({ fieldname: "status", operator: "equals", value: "Open" });
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "desc" }]);
	});

	it("is seeded, with its sort, only once the stored settings are in", async () => {
		let answerSettings!: () => void;
		fake.runMethod.mockImplementationOnce(
			(method: string, args: Record<string, any>) =>
				new Promise((done) => (answerSettings = () => done(answer(method, args))))
		);
		await mount("/lead");
		expect(page.seeded.value).toBe(false);
		expect(page.sort.value).toEqual([]);

		answerSettings();
		await settle();
		expect(page.seeded.value).toBe(true);
		expect(page.sort.value).toEqual([{ fieldname: "amount", direction: "asc" }]);
	});

	it("builds the list once meta is in, from offset zero, with the count beside it", async () => {
		await mount("/lead");
		await settle();
		expect(page.hasCounts.value).toBe(false);
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
		expect(fake.listDocuments.mock.calls[0]).toEqual([
			"Lead",
			{ fields: ["name", "title", "status", "amount"], filters: {}, order_by: "amount asc", start: 0, limit: 20 },
			{ include: ["count", "favourites"] },
		]);
		fake.lists[0].data = [];
		await settle();
		expect(page.totalCount.value).toBe(42);
		expect(page.totalCapped.value).toBe(false);
		expect(page.hasCounts.value).toBe(true);
	});
});

describe("Track Seen", () => {
	it("asks for _seen and marks the title cell of a row the user has not opened", async () => {
		fake.meta = { ...fake.meta!, track_seen: 1 } as typeof fake.meta;
		await mount("/lead");
		await settle();
		expect(fake.listDocuments.mock.calls[0][1].fields).toEqual(["name", "title", "status", "amount", "_seen"]);
		const row = { name: "LEAD-1", _seen: '["bob@example.com"]' };
		expect(page.seenClassOf(row, "title")).toContain("font-medium");
		expect(page.seenClassOf(row, "status")).toBe("");
		expect(page.seenClassOf({ ...row, _seen: '["alice@example.com"]' }, "title")).not.toContain("font-medium");
	});

	it("leaves a doctype that does not track seen as it is", async () => {
		await mount("/lead");
		await settle();
		expect(fake.listDocuments.mock.calls[0][1].fields).not.toContain("_seen");
		expect(page.seenClassOf({ name: "LEAD-1" }, "title")).toBe("");
	});
});

describe("the view", () => {
	it("is the view opened, with the stored settings, the page's changes on top and the URL's filters and sort", async () => {
		opened = { key: "board", label: "Board", type: "Kanban", layer: "own", applies: true };
		fake.tiers = { site: null, user: { sort: [{ fieldname: "title", direction: "asc" }], lane: "status" } };
		await mount("/lead?status=Open&_sort=amount%20desc");
		const { view } = page;

		expect([view.doctype, view.key, view.type, view.layer]).toEqual(["Lead", "board", "Kanban", "own"]);
		expect(view.settings.value).toMatchObject({ lane: "status" });
		expect(view.filters.value[0]).toMatchObject({ fieldname: "status", value: "Open" });
		expect(view.sort.value).toEqual([{ fieldname: "amount", direction: "desc" }]);

		view.update({ lane: "title", cards: 3 });
		expect(view.settings.value).toMatchObject({ lane: "title", cards: 3 });
		expect(view.settings.value.sort).toEqual([{ fieldname: "title", direction: "asc" }]);
	});

	it("is the plain List view when no view is opened", async () => {
		await mount("/lead");
		expect([page.view.key, page.view.type, page.view.layer]).toEqual(["list", "List", null]);
	});

	it("keeps a type's own keys in page state, marks the view modified, and writes none of them to the URL", async () => {
		await mount("/lead");
		const { view } = page;
		expect(view.modified.value).toBe(false);

		view.update({ some_key: 1 });
		await nextTick();
		expect(view.settings.value).toMatchObject({ some_key: 1 });
		expect(view.modified.value).toBe(true);
		await settle();
		expect(router.currentRoute.value.query).toEqual({});

		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ status: "Open" });
	});
});

describe("the tiers", () => {
	it("fetches the rows beside meta and seeds the person's columns over the site's sort", async () => {
		fake.tiers = {
			site: { columns: [{ fieldname: "amount" }], sort: [{ fieldname: "title", direction: "desc" }] },
			user: { columns: [{ fieldname: "status", width: "80px" }, { fieldname: "title" }] },
		};
		await mount("/lead");
		expect(fake.runMethod).toHaveBeenCalledWith(`${SETTINGS_API}.get`, { doctype: "Lead", type: "List" });
		expect(page.columns.value).toEqual([
			{ fieldname: "status", label: "Status", align: "left", width: "80px" },
			{ fieldname: "title", label: "Title", align: "left" },
		]);
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "desc" }]);
		expect(page.columnsCustomized.value).toBe(true);
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
		expect(fake.lists[0].query).toMatchObject({ fields: ["name", "status", "title"], order_by: "title desc" });
	});

	it("drops a stored fieldname meta lacks or the person cannot read, and falls back when none is left", async () => {
		fake.meta!.fields = [...FIELDS, { fieldname: "secret", label: "Secret", fieldtype: "Data", permlevel: 1 }];
		fake.meta!.permissions = [{ role: "System Manager", permlevel: 1, read: 1 }];
		fake.tiers = { site: null, user: { columns: [{ fieldname: "secret" }, { fieldname: "gone" }], sort: [{ fieldname: "secret", direction: "asc" }] } };
		await mount("/lead");
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["title", "status", "amount"]);
		expect(page.sort.value).toEqual([{ fieldname: "amount", direction: "asc" }]);
	});

	it("knows a standard column's fieldtype, which meta does not list", async () => {
		await mount("/lead");
		expect(page.fieldOf("modified")?.fieldtype).toBe("Datetime");
		expect(page.fieldOf("amount")?.fieldtype).toBe("Currency");
		expect(page.fieldOf("gone")).toBeUndefined();
	});

	it("asks for the field a Currency column takes its currency from, when the person can read it", async () => {
		const currency = { fieldname: "currency", label: "Currency", fieldtype: "Link", options: "Currency" };
		const amount = { ...FIELDS[2], options: "currency" };
		fake.meta!.fields = [FIELDS[0], FIELDS[1], amount, currency];
		await mount("/lead");
		await settle();
		expect(fake.lists[0].query.fields).toEqual(["name", "title", "status", "amount", "currency"]);
		expect(page.currencyOf("amount")).toEqual({ key: "currency", select: "currency" });

		fake.meta!.fields = [FIELDS[0], FIELDS[1], amount, { ...currency, permlevel: 1 }];
		fake.meta!.permissions = [{ role: "System Manager", permlevel: 1, read: 1 }];
		resetDoctypeMeta();
		clearDataCache();
		fake.lists = [];
		await mount("/lead");
		await settle();
		expect(fake.lists[0].query.fields).toEqual(["name", "title", "status", "amount"]);
		expect(page.currencyOf("amount")).toBeUndefined();
	});

	it("asks for the fields a column's badge function reads", async () => {
		fake.meta!.fields = [...FIELDS, { fieldname: "due", label: "Due", fieldtype: "Date" }];
		fake.columnItems = [{ name: "title" }, { name: "status", fields: ["due", "amount"] }];
		await mount("/lead");
		await settle();
		expect(fake.lists[0].query.fields).toEqual(["name", "title", "status", "due", "amount"]);
	});

	it("applies a badge's filters over the view's conditions on the same fields", async () => {
		await mount("/lead");
		await settle();
		const title = { field: FIELDS[0], fieldname: "title", operator: "equals", value: "A" };
		page.filters.value = [title, { field: FIELDS[1], fieldname: "status", operator: "equals", value: "Open" }] as never;

		page.applyBadgeFilters([["status", "=", "Closed"]]);

		expect(page.filters.value).toEqual([title, { field: expect.objectContaining({ fieldname: "status" }), fieldname: "status", operator: "equals", value: "Closed" }]);
	});

	it("applies none of a badge's filters when one names an unknown field or operator", async () => {
		const log = vi.spyOn(console, "error").mockImplementation(() => {});
		await mount("/lead");
		await settle();

		page.applyBadgeFilters([["status", "=", "Closed"], ["typo", "=", 1]]);
		page.applyBadgeFilters([["status", "contains", "x"]] as never);

		expect(page.filters.value).toEqual([]);
		expect(log).toHaveBeenCalledTimes(2);
		log.mockRestore();
	});

	it("reads a Check's 1 as the filter bar's Yes", async () => {
		fake.meta!.fields = [...FIELDS, { fieldname: "overdue", label: "Overdue", fieldtype: "Check" }];
		await mount("/lead");
		await settle();

		page.applyBadgeFilters([["overdue", "=", 1]]);

		expect(page.filters.value).toMatchObject([{ fieldname: "overdue", operator: "equals", value: "Yes" }]);
	});

	it("asks for a Link column's target title and keys it the way the form's link titles are", async () => {
		const deal = { fieldname: "deal", label: "Deal", fieldtype: "Link", options: "CRM Deal", in_list_view: 1, link_title: "organization" };
		fake.meta!.fields = [FIELDS[0], deal];
		await mount("/lead");
		await settle();
		expect(fake.lists[0].query.fields).toEqual(["name", "title", "deal", "deal.organization as deal__title"]);
		fake.lists[0].data = [
			{ name: "LEAD-1", deal: "D-1", deal__title: "Acme" },
			{ name: "LEAD-2", deal: "D-2", deal__title: null },
			{ name: "LEAD-3", deal: null },
		];
		await settle();
		expect(page.linkTitles.value).toEqual({ "CRM Deal::D-1": "Acme" });
	});

	it("writes the person's column change after the debounce, without labels, and not a rename alone", async () => {
		await mount("/lead");
		await settle();
		page.columns.value = page.columns.value.map((c) => (c.fieldname === "title" ? { ...c, label: "Mine" } : c));
		await settle();
		expect(writes()).toEqual([]);
		page.resizeColumn("status", "70px");
		await settle();
		expect(writes()).toEqual([]);
		await useListSettings("Lead").flush();
		expect(writes()).toEqual([
			[`${SETTINGS_API}.save`, { doctype: "Lead", type: "List", scope: "user", settings: { columns: [{ fieldname: "title" }, { fieldname: "status", width: "70px" }, { fieldname: "amount" }] } }],
		]);
		expect(page.columnsCustomized.value).toBe(true);
	});

	it("never writes a filter or a page size", async () => {
		await mount("/lead");
		await settle();
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		page.pageSize.value = 100;
		await settleQuery();
		await useListSettings("Lead").flush();
		expect(writes()).toEqual([]);
	});

	it("drops _sort from the URL once the person's sort has landed as their default", async () => {
		await mount("/lead");
		await settle();
		page.sort.value = [{ fieldname: "status", direction: "desc" }];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ _sort: "status desc" });
		await useListSettings("Lead").flush();
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
		expect(page.sort.value).toEqual([{ fieldname: "status", direction: "desc" }]);
	});

	it("writes the person's sort and never one the URL carried in", async () => {
		await mount("/lead?_sort=status%20desc");
		await settle();
		await router.replace({ query: { _sort: "title asc" } });
		await settle();
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "asc" }]);
		await useListSettings("Lead").flush();
		expect(writes()).toEqual([]);
		page.sort.value = [{ fieldname: "amount", direction: "desc" }];
		await settle();
		await useListSettings("Lead").flush();
		expect(writes()[0][1]).toMatchObject({ scope: "user", settings: { sort: [{ fieldname: "amount", direction: "desc" }] } });
	});

	it("writes the quick filter's fields when customizing ends, not while it runs", async () => {
		await mount("/lead");
		await settle();
		page.customizing.value = true;
		page.quickFilterFields.value = [{ fieldname: "status", value: "status", label: "Status", fieldtype: "Select" }];
		await settle();
		await useListSettings("Lead").flush();
		expect(writes()).toEqual([]);
		page.customizing.value = false;
		await settle();
		await useListSettings("Lead").flush();
		expect(writes()[0][1]).toMatchObject({ settings: { quick_filter_fields: ["status"] } });
	});

	it("resets the person's columns to the site's, and a site act reaches the page too", async () => {
		fake.tiers = { site: { columns: [{ fieldname: "amount" }] }, user: { columns: [{ fieldname: "status" }] } };
		await mount("/lead");
		await settle();
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "" } as never];
		await settle();
		await page.resetColumns();
		expect(page.filters.value).toHaveLength(1);
		expect(writes()[0]).toEqual([`${SETTINGS_API}.reset`, { doctype: "Lead", type: "List", scope: "user", key: "columns" }]);
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["amount"]);
		expect(page.columnsCustomized.value).toBe(false);
		await page.saveForSite({ sort: [{ fieldname: "status", direction: "asc" }] });
		expect(writes()[1][1]).toMatchObject({ scope: "site", settings: { sort: [{ fieldname: "status", direction: "asc" }] } });
		expect(page.sort.value).toEqual([{ fieldname: "status", direction: "asc" }]);
		await page.resetForSite("columns");
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["title", "status", "amount"]);
		await useListSettings("Lead").flush();
		expect(writes()).toHaveLength(3);
	});
});

describe("the app's file", () => {
	const OPEN = [["status", "=", "Open"]];

	it("seeds columns, sort and filters under the site's and the person's rows", async () => {
		fake.tiers = {
			app: { columns: [{ fieldname: "amount" }], sort: [{ fieldname: "title", direction: "desc" }], filters: OPEN },
			site: null,
			user: { columns: [{ fieldname: "status" }] },
		};
		await mount("/lead");
		expect(page.columns.value.map((column) => column.fieldname)).toEqual(["status"]);
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "desc" }]);
		expect(page.filters.value).toMatchObject([{ fieldname: "status", operator: "equals", value: "Open" }]);
		expect(fake.lists[0].query).toMatchObject({ filters: { status: ["=", "Open"] } });
	});

	it("leaves the URL bare and the view unmodified while its filters are the file's", async () => {
		fake.tiers = { app: { filters: OPEN }, site: null, user: null };
		await mount("/lead");
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
		expect(page.view.modified.value).toBe(false);
	});

	it("spells a change of the filters, and lets the person clear them", async () => {
		fake.tiers = { app: { filters: OPEN }, site: null, user: null };
		await mount("/lead");
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Closed" } as never];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ status: "Closed" });
		expect(page.view.modified.value).toBe(true);
		page.filters.value = [];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ _filters: "none" });
		expect(page.filters.value).toEqual([]);
		expect(page.view.modified.value).toBe(true);
	});

	it("keeps the filters cleared across a reload of the URL", async () => {
		fake.tiers = { app: { filters: OPEN }, site: null, user: null };
		await mount("/lead?_filters=none");
		expect(page.filters.value).toEqual([]);
		expect(fake.lists[0].query).not.toHaveProperty("filters.status");
	});

	it("writes no _filters key when the file has no filters", async () => {
		await mount("/lead");
		page.filters.value = [];
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
	});

	it("gives way to the filters a URL names", async () => {
		fake.tiers = { app: { filters: OPEN }, site: null, user: null };
		await mount("/lead?status=Closed");
		expect(page.filters.value).toMatchObject([{ fieldname: "status", value: "Closed" }]);
	});

	it("drops a filter on a field meta lacks", async () => {
		fake.tiers = { app: { filters: [["gone", "=", "x"]] }, site: null, user: null };
		await mount("/lead");
		expect(page.filters.value).toEqual([]);
	});
});

describe("the URL", () => {
	it("writes a filter to the query and keeps a key it does not own", async () => {
		await mount("/lead?view=kanban");
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ view: "kanban", status: "Open" });
	});

	it("writes a sort only when it is not the default", async () => {
		await mount("/lead");
		page.sort.value = [{ fieldname: "status", direction: "desc" }];
		await settle();
		expect(router.currentRoute.value.query).toEqual({ _sort: "status desc" });
		page.sort.value = [{ fieldname: "amount", direction: "asc" }];
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
	});

	it("reads a query it did not write, and leaves a filter still being typed alone", async () => {
		await mount("/lead");
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "" } as never];
		await settle();
		expect(page.filters.value).toHaveLength(1);
		await router.replace({ query: { status: "Closed" } });
		await settle();
		expect(page.filters.value).toHaveLength(1);
		expect(page.filters.value[0]).toMatchObject({ value: "Closed" });
	});
});

describe("createValues", () => {
	it("starts a new record with the list's equals filters from the URL", async () => {
		await mount(`/lead?status=Open&amount=${encodeURIComponent(JSON.stringify([">", "100"]))}`);
		expect(page.filters.value).toHaveLength(2);
		expect(page.createValues.value).toEqual({ status: "Open" });
	});

	it("follows the filters as the person changes them", async () => {
		await mount("/lead");
		expect(page.createValues.value).toEqual({});
		page.filters.value = [{ fieldname: "title", operator: "equals", value: "Big deal" } as never];
		await settle();
		expect(page.createValues.value).toEqual({ title: "Big deal" });
	});
});

describe("the rows", () => {
	it("keeps the selection across a load-more and a reload, and drops the rows that left", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await settle();
		page.selection.value = ["LEAD-1", "LEAD-2"];
		page.next();
		fake.lists[1].data = rowsNamed(20, 20);
		await settle();
		expect(page.selection.value).toEqual(["LEAD-1", "LEAD-2"]);
		page.reload();
		await settle();
		expect(page.selection.value).toEqual(["LEAD-1", "LEAD-2"]);
		fake.lists[2].data = rowsNamed(40, 2);
		await settle();
		expect(page.selection.value).toEqual(["LEAD-2"]);
	});

	it("rebuilds the list for a changed filter after the typing debounce, keeping the rows it hides selected", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = [{ name: "LEAD-1" }];
		await nextTick();
		page.selection.value = ["LEAD-1"];
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settle();
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
		await settleQuery();
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);
		expect(fake.lists[1].query.filters).toEqual({ status: ["=", "Open"] });
		expect(page.rows.value).toEqual([]);
		expect(page.selection.value).toEqual(["LEAD-1"]);
	});

	it("keeps the page size in the history entry and a bigger one fetches only the missing rows", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.pageSize.value = 100;
		await settleQuery();
		expect((history.state as { list?: unknown }).list).toEqual({ pageSize: 100 });
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);
		expect(fake.lists[1].query).toMatchObject({ start: 20, limit: 80 });
		fake.lists[1].data = rowsNamed(80, 20);
		await nextTick();
		expect(page.rows.value).toHaveLength(100);
		page.next();
		expect(fake.lists[2].query).toMatchObject({ start: 100, limit: 100 });
	});

	it("choosing the size already chosen after a Load More trims the list back to it", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.next();
		fake.lists[1].data = rowsNamed(20, 20);
		await nextTick();
		expect(page.rows.value).toHaveLength(40);

		page.show(20);
		await nextTick();
		expect(page.rows.value).toHaveLength(20);
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);

		// Nothing beyond the size is shown, so the same click again asks the server for nothing.
		page.show(20);
		await nextTick();
		expect(page.rows.value).toHaveLength(20);
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);
	});

	it("a bigger page size while the first page is in flight starts the list over", async () => {
		await mount("/lead");
		await settle();
		page.pageSize.value = 500;
		await settleQuery();
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);
		expect(fake.lists[1].query).toMatchObject({ start: 0, limit: 500 });
	});

	it("a smaller page size shows fewer of the loaded rows, and next reveals them before fetching", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(100);
		fake.lists[0].hasNextPage = false;
		await nextTick();
		page.pageSize.value = 20;
		await settleQuery();
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
		expect(page.rows.value).toHaveLength(20);
		expect(page.hasNextPage.value).toBe(true);
		page.next();
		await nextTick();
		expect(page.rows.value).toHaveLength(40);
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
	});

	it("a return to the same query paints the cached rows and count, then reads them again at once", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.next();
		await nextTick();
		expect(fake.lists[1].query).toMatchObject({ start: 20, limit: 20 });
		fake.lists[1].data = rowsNamed(20, 20);
		await settle();

		app!.unmount();
		app = null;
		fake.listDocuments.mockClear();
		fake.lists = [];
		await mount("/lead");
		expect(page.loading.value).toBe(false);
		expect(page.rows.value).toHaveLength(40);
		expect(page.hasCounts.value).toBe(true);
		expect(page.totalCount.value).toBe(42);
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
		expect(fake.lists[0].query).toMatchObject({ start: 0, limit: 40 });
		expect(fake.lists[0].include).toEqual(["count", "favourites"]);

		app!.unmount();
		app = null;
		fake.listDocuments.mockClear();
		fake.lists = [];
		await mount("/lead?status=Open");
		expect(page.loading.value).toBe(true);
		expect(fake.lists[0].query).toMatchObject({ start: 0, limit: 20 });
	});

	it("the background read swaps rows, count and selection in one step", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await settle();
		app!.unmount();
		app = null;
		fake.lists = [];
		await mount("/lead");
		page.selection.value = ["LEAD-0", "LEAD-5"];
		const seen: [string, number][] = [];
		watch(page.rows, (rows) => seen.push([rows[0].name, page.totalCount.value]));
		fake.lists[0].count = 41;
		fake.lists[0].data = rowsNamed(20, 1);
		await settle();
		expect(page.rows.value[0].name).toBe("LEAD-1");
		expect(page.totalCount.value).toBe(41);
		expect(page.selection.value).toEqual(["LEAD-5"]);
		expect(seen).toEqual([["LEAD-1", 41]]);
	});

	it("a page size changed while a filter waits is remembered under the rows' own query", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		const before = page.rowsKey();
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settle();
		page.pageSize.value = 100;
		await settle();
		expect(page.rowsKey()).toBe(before);
		expect(recallRows("Lead", before)).toMatchObject({ pageSize: 100 });
		await settleQuery();
		expect(page.rowsKey()).not.toBe(before);
		expect(recallRows("Lead", page.rowsKey())).toMatchObject({ pageSize: 100 });
	});

	it("a new query on the same entry drops the entry's scroll offset", async () => {
		await mount("/lead");
		await settle();
		writeListMemory({ scrollTop: 240 });
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settleQuery();
		expect(readListMemory().scrollTop).toBe(0);
	});

	it("a delete's reload keeps the rows shown", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.next();
		await nextTick();
		fake.lists[1].data = rowsNamed(20, 20);
		await nextTick();
		page.selection.value = ["LEAD-0"];
		await page.deleteSelection();
		expect(fake.lists[2].query).toMatchObject({ start: 0, limit: 40 });
	});

	it("next waits for a page in flight", async () => {
		await mount("/lead");
		await settle();
		page.next();
		expect(fake.listDocuments).toHaveBeenCalledTimes(1);
	});

	it("links a row to its record through the shell's route", async () => {
		await mount("/lead");
		expect(router.resolve(page.rowLink({ name: "LEAD-1" })).path).toBe("/lead/LEAD-1");
	});
});

describe("the count", () => {
	it("reads a capped total as a floor, and asks for the exact one on request", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].count = 1000;
		fake.lists[0].capped = true;
		fake.lists[0].data = rowsNamed(20);
		await settle();
		expect(page.totalCount.value).toBe(1000);
		expect(page.totalCapped.value).toBe(true);
		expect(page.totalUnknown.value).toBe(false);
		await page.countExact();
		expect(fake.countDocuments).toHaveBeenCalledWith("Lead", { filters: {} });
		expect(page.totalCount.value).toBe(1234);
		expect(page.totalCapped.value).toBe(false);
	});

	it("shows the rows as a floor when the server gave up counting, and keeps the next page reachable", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].count = null;
		fake.lists[0].data = [{ name: "LEAD-1" }];
		await settle();
		expect(page.hasCounts.value).toBe(true);
		expect(page.totalUnknown.value).toBe(true);
		expect(page.totalCount.value).toBe(1);
		expect(page.totalCapped.value).toBe(true);
		expect(page.hasNextPage.value).toBe(true);
	});
});

describe("deleteSelection", () => {
	it("deletes the selection in one bulk call through the shared runner, clears the selection and reloads", async () => {
		await mount("/lead");
		await settle();
		fake.bulkDelete.mockResolvedValueOnce({ data: { total: 2, done: ["LEAD-1", "LEAD-2"], failed: [] } });
		page.selection.value = ["LEAD-1", "LEAD-2"];
		await page.deleteSelection();
		expect(fake.bulkDelete.mock.calls).toEqual([["Lead", { names: ["LEAD-1", "LEAD-2"] }]]);
		expect(page.selection.value).toEqual([]);
		expect(fake.listDocuments).toHaveBeenCalledTimes(2);
	});

	it("deletes every record the filters show after Select all, not the loaded names", async () => {
		await mount("/lead");
		await settle();
		fake.bulkDelete.mockResolvedValueOnce({ data: { total: 600, done: ["LEAD-1"], failed: [] } });
		page.selection.value = ["LEAD-1"];
		page.scope.selectAll();
		await page.deleteSelection();
		expect(fake.bulkDelete.mock.calls).toEqual([["Lead", { filters: {} }]]);
		expect(page.scope.all.value).toBe(false);
		expect(page.selection.value).toEqual([]);
	});

	it("opens the result panel on a failure, and Select failed puts the failed names back in the selection", async () => {
		const { bulkPanel } = await import("@/shell/bulkOutcome");
		await mount("/lead");
		await settle();
		fake.bulkDelete.mockResolvedValueOnce({
			data: { total: 2, done: ["LEAD-1"], failed: [{ name: "LEAD-2", error: "Not permitted" }] },
		});
		page.selection.value = ["LEAD-1", "LEAD-2"];
		await page.deleteSelection();
		expect(bulkPanel.value?.failed).toEqual([{ name: "LEAD-2", error: "Not permitted" }]);
		bulkPanel.value?.select?.(["LEAD-2"]);
		expect(page.selection.value).toEqual(["LEAD-2"]);
		bulkPanel.value = null;
	});

	it("hands a run that went to the background to the tray", async () => {
		const { bulkRunMeta } = await import("@/shell/bulkOutcome");
		await mount("/lead");
		await settle();
		fake.bulkDelete.mockResolvedValueOnce({ data: { task_id: "T-1", job_id: "J-1" } });
		page.selection.value = ["LEAD-1"];
		await page.deleteSelection();
		expect(bulkRunMeta.get("T-1")?.label).toBe("Delete");
	});

	it("keeps the selection when the whole run is refused", async () => {
		await mount("/lead");
		await settle();
		fake.bulkDelete.mockRejectedValueOnce(new Error("Bulk actions are off"));
		page.selection.value = ["LEAD-1"];
		await expect(page.deleteSelection()).rejects.toThrow("Bulk actions are off");
		expect(page.selection.value).toEqual(["LEAD-1"]);
	});
});

describe("after a DocType change", () => {
	/** The first visit, then the change: the next mount shows the stale meta and settings. */
	async function changeWhileAway() {
		fake.tiers = { site: null, user: { columns: [{ fieldname: "status" }, { fieldname: "title" }] } };
		await mount("/lead");
		app?.unmount();
		markDoctypeMetaStale("Lead");
		markListSettingsStale("Lead");
		fake.meta = { ...fake.meta!, fields: FIELDS.map((f) => (f.fieldname === "status" ? { ...f, label: "Stage" } : f)) };
		fake.tiers = { site: { sort: [{ fieldname: "title", direction: "desc" }] }, user: { columns: [{ fieldname: "amount" }] } };
		let answerSettings!: () => void;
		fake.runMethod.mockImplementationOnce(
			(method: string, args: Record<string, any>) =>
				new Promise((done) => (answerSettings = () => done(answer(method, args))))
		);
		await mount("/lead");
		return () => answerSettings();
	}

	it("shows the stale columns at once, then the fresh meta, columns and sort in one step", async () => {
		const answerSettings = await changeWhileAway();
		expect(page.seeded.value).toBe(true);
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["status", "title"]);
		expect(useDoctypeMeta("Lead").meta.value!.fields![1].label).toBe("Status");

		const seen: string[] = [];
		watch(
			[page.columns, page.sort, () => useDoctypeMeta("Lead").meta.value?.fields?.[1].label],
			([columns, sort, label]) =>
				seen.push(`${columns.map((c) => c.fieldname)}|${sort.map((s) => s.fieldname)}|${label}`)
		);
		answerSettings();
		await settle();

		expect(seen).toEqual(["amount|title|Stage"]);
		expect(writes()).toEqual([]);
	});

	it("keeps a column the person changed before the fresh settings arrived, and takes the fresh sort", async () => {
		const answerSettings = await changeWhileAway();
		page.columns.value = page.columns.value.filter((c) => c.fieldname === "title");
		await settle();

		answerSettings();
		await settle();

		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["title"]);
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "desc" }]);
	});
});

describe("filtersFit", () => {
	const on = (fieldname: string, operator: string, value: unknown) => ({ fieldname, operator, value }) as never;

	it("is false when two conditions share a field, as the dict keeps one", () => {
		expect(filtersFit([on("status", "equals", "Open"), on("priority", "equals", "High")])).toBe(true);
		expect(filtersFit([on("amount", ">=", 5), on("amount", "<=", 9)])).toBe(false);
	});
});
