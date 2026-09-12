// The composable as claims: what seeds it, what it writes to the URL, when it rebuilds the list,
// and what a delete does. frappe-ui's data layer is faked; the router and history are real.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick, reactive, type App } from "vue";
import { createRouter, createWebHistory, type Router } from "vue-router";

const fake = vi.hoisted(() => ({
	meta: null as Record<string, unknown> | null,
	contributed: [] as { columns?: { fieldname: string; width?: number }[] }[],
	lists: [] as any[],
	tiers: { site: null, user: null } as { site: unknown; user: unknown },
	useList: vi.fn(),
	call: vi.fn(),
	remove: vi.fn(),
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<object>()),
	call: fake.call,
	useList: fake.useList,
	createResource: ({ url }: { url: string }) => ({
		get data() {
			if (url.endsWith("get_current_user_roles")) return ["Desk User"];
			return fake.meta && { docs: [fake.meta] };
		},
		loading: false,
		fetch() {},
		reload() {},
	}),
}));

vi.mock("@/contributions/registry", () => ({
	listHandlersFor: () => fake.contributed.map((handlers) => ({ app: "crm", handlers })),
}));

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { forgetRows, readListMemory, recallRows, writeListMemory } from "../pageState";
import { useListPage, type ListPage } from "../useListPage";
import { resetListSettings, useListSettings } from "../useListSettings";

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
let page: ListPage;

function fakeList() {
	const list = reactive({
		data: null as Record<string, unknown>[] | null,
		error: null,
		hasNextPage: true,
		loading: true,
		next: vi.fn(),
		delete: { submit: fake.remove },
	});
	fake.lists.push(list);
	return list;
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
				page = useListPage("Lead");
				return () => null;
			},
		})
	);
	app.use(router);
	app.mount(root);
	await nextTick();
}

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** The count answers 42; a settings call answers the tiers, a write patched in. */
function answer(method: string, args: Record<string, any>) {
	if (method === "frappe.client.get_count") return Promise.resolve(42);
	if (method.endsWith(".save")) {
		const row = (fake.tiers[args.scope as "site" | "user"] ?? {}) as Record<string, unknown>;
		fake.tiers = { ...fake.tiers, [args.scope]: { ...row, ...args.settings } };
	}
	if (method.endsWith(".reset")) {
		const row = { ...(fake.tiers[args.scope as "site" | "user"] as Record<string, unknown>) };
		delete row[args.key];
		fake.tiers = { ...fake.tiers, [args.scope]: Object.keys(row).length ? row : null };
	}
	return Promise.resolve(fake.tiers);
}

function writes() {
	return fake.call.mock.calls.filter(([method]) => method.startsWith(SETTINGS_API) && !method.endsWith(".get"));
}

/** A changed query waits out the typing debounce before it builds a list. */
async function settleQuery() {
	await new Promise((resolve) => setTimeout(resolve, 350));
	await settle();
}

beforeEach(() => {
	resetDoctypeMeta();
	resetUserRoles();
	resetListSettings();
	forgetRows("Lead");
	history.replaceState(null, "");
	fake.meta = { name: "Lead", title_field: "title", sort_field: "amount", sort_order: "ASC", fields: FIELDS };
	fake.contributed = [];
	fake.lists = [];
	fake.tiers = { site: null, user: null };
	fake.useList.mockReset().mockImplementation(fakeList);
	fake.call.mockReset().mockImplementation(answer);
	fake.remove.mockReset().mockResolvedValue("ok");
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

	it("takes a contributed list.js's columns over meta", async () => {
		fake.contributed = [{ columns: [{ fieldname: "status" }, { fieldname: "title" }] }];
		await mount("/lead");
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["status", "title"]);
		expect(page.columnsCustomized.value).toBe(false);
	});

	it("builds the list once meta is in, from offset zero, with the count beside it", async () => {
		await mount("/lead");
		await settle();
		expect(page.totalCapped.value).toBe(false);
		expect(fake.useList).toHaveBeenCalledTimes(1);
		expect(fake.useList.mock.calls[0][0]).toMatchObject({
			doctype: "Lead",
			fields: ["name", "title", "status", "amount"],
			filters: {},
			orderBy: "amount asc",
			start: 0,
			limit: 20,
			refetch: false,
		});
		expect(fake.call).toHaveBeenCalledWith("frappe.client.get_count", { doctype: "Lead", filters: {}, limit: 1001 });
		expect(page.totalCount.value).toBe(42);
		expect(page.hasCounts.value).toBe(true);
	});
});

describe("the tiers", () => {
	it("fetches the rows beside meta and seeds the person's columns over the site's sort", async () => {
		fake.tiers = {
			site: { columns: [{ fieldname: "amount" }], sort: [{ fieldname: "title", direction: "desc" }] },
			user: { columns: [{ fieldname: "status", width: "80px" }, { fieldname: "title" }] },
		};
		await mount("/lead");
		expect(fake.call).toHaveBeenCalledWith(`${SETTINGS_API}.get`, { doctype: "Lead", type: "List" });
		expect(page.columns.value).toEqual([
			{ fieldname: "status", label: "Status", align: "left", width: "80px" },
			{ fieldname: "title", label: "Title", align: "left" },
		]);
		expect(page.sort.value).toEqual([{ fieldname: "title", direction: "desc" }]);
		expect(page.columnsCustomized.value).toBe(true);
		await settle();
		expect(router.currentRoute.value.query).toEqual({});
		expect(fake.useList.mock.calls[0][0]).toMatchObject({ fields: ["name", "status", "title"], orderBy: "title desc" });
	});

	it("drops a stored fieldname meta lacks or the person cannot read, and falls back when none is left", async () => {
		fake.meta!.fields = [...FIELDS, { fieldname: "secret", label: "Secret", fieldtype: "Data", permlevel: 1 }];
		fake.meta!.permissions = [{ role: "System Manager", permlevel: 1, read: 1 }];
		fake.tiers = { site: null, user: { columns: [{ fieldname: "secret" }, { fieldname: "gone" }], sort: [{ fieldname: "secret", direction: "asc" }] } };
		await mount("/lead");
		expect(page.columns.value.map((c) => c.fieldname)).toEqual(["title", "status", "amount"]);
		expect(page.sort.value).toEqual([{ fieldname: "amount", direction: "asc" }]);
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

describe("the rows", () => {
	it("keeps the selection across a load-more, minus any row that left", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = [{ name: "LEAD-1" }, { name: "LEAD-2" }];
		await nextTick();
		page.selection.value = ["LEAD-1", "LEAD-2"];
		fake.lists[0].data = [{ name: "LEAD-2" }, { name: "LEAD-3" }];
		await nextTick();
		expect(page.selection.value).toEqual(["LEAD-2"]);
	});

	it("rebuilds the list for a changed filter after the typing debounce, with no selection", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = [{ name: "LEAD-1" }];
		await nextTick();
		page.selection.value = ["LEAD-1"];
		page.filters.value = [{ fieldname: "status", operator: "equals", value: "Open" } as never];
		await settle();
		expect(fake.useList).toHaveBeenCalledTimes(1);
		await settleQuery();
		expect(fake.useList).toHaveBeenCalledTimes(2);
		expect(fake.useList.mock.calls[1][0].filters).toEqual({ status: ["=", "Open"] });
		expect(page.selection.value).toEqual([]);
	});

	it("keeps the page size in the history entry and a bigger one fetches only the missing rows", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.pageSize.value = 100;
		await settleQuery();
		expect((history.state as { list?: unknown }).list).toEqual({ pageSize: 100 });
		expect(fake.useList).toHaveBeenCalledTimes(2);
		expect(fake.useList.mock.calls[1][0]).toMatchObject({ start: 20, limit: 80 });
		fake.lists[1].data = rowsNamed(80, 20);
		await nextTick();
		expect(page.rows.value).toHaveLength(100);
		page.next();
		expect(fake.useList.mock.calls[2][0]).toMatchObject({ start: 100, limit: 100 });
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
		expect(fake.useList).toHaveBeenCalledTimes(2);

		// Nothing beyond the size is shown, so the same click again asks the server for nothing.
		page.show(20);
		await nextTick();
		expect(page.rows.value).toHaveLength(20);
		expect(fake.useList).toHaveBeenCalledTimes(2);
	});

	it("a bigger page size while the first page is in flight starts the list over", async () => {
		await mount("/lead");
		await settle();
		page.pageSize.value = 500;
		await settleQuery();
		expect(fake.useList).toHaveBeenCalledTimes(2);
		expect(fake.useList.mock.calls[1][0]).toMatchObject({ start: 0, limit: 500 });
	});

	it("a smaller page size shows fewer of the loaded rows, and next reveals them before fetching", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(100);
		fake.lists[0].hasNextPage = false;
		await nextTick();
		page.pageSize.value = 20;
		await settleQuery();
		expect(fake.useList).toHaveBeenCalledTimes(1);
		expect(page.rows.value).toHaveLength(20);
		expect(page.hasNextPage.value).toBe(true);
		page.next();
		await nextTick();
		expect(page.rows.value).toHaveLength(40);
		expect(fake.useList).toHaveBeenCalledTimes(1);
	});

	it("a return to the same query shows as many rows as before, by one request", async () => {
		await mount("/lead");
		await settle();
		fake.lists[0].data = rowsNamed(20);
		await nextTick();
		page.next();
		await nextTick();
		expect(fake.useList.mock.calls[1][0]).toMatchObject({ start: 20, limit: 20 });

		app!.unmount();
		app = null;
		fake.useList.mockClear();
		await mount("/lead");
		await settle();
		expect(fake.useList).toHaveBeenCalledTimes(1);
		expect(fake.useList.mock.calls[0][0]).toMatchObject({ start: 0, limit: 40 });

		app!.unmount();
		app = null;
		fake.useList.mockClear();
		await mount("/lead?status=Open");
		await settle();
		expect(fake.useList.mock.calls[0][0]).toMatchObject({ start: 0, limit: 20 });
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
		expect(recallRows("Lead", before)).toMatchObject({ pageSize: 100, shown: 100 });
		await settleQuery();
		expect(page.rowsKey()).not.toBe(before);
		expect(recallRows("Lead", page.rowsKey())).toMatchObject({ shown: 100 });
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
		expect(fake.useList.mock.calls[2][0]).toMatchObject({ start: 0, limit: 40 });
	});

	it("next waits for a page in flight", async () => {
		await mount("/lead");
		await settle();
		page.next();
		expect(fake.useList).toHaveBeenCalledTimes(1);
	});

	it("links a row to its record through the shell's route", async () => {
		await mount("/lead");
		expect(router.resolve(page.rowLink({ name: "LEAD-1" })).path).toBe("/lead/LEAD-1");
	});
});

describe("the count", () => {
	it("reads a total past the bound as capped", async () => {
		fake.call.mockResolvedValue(1001);
		await mount("/lead");
		await settle();
		expect(page.totalCount.value).toBe(1000);
		expect(page.totalCapped.value).toBe(true);
	});

	it("shows the rows as a floor when the count fails, and keeps the next page reachable", async () => {
		fake.call.mockRejectedValue(new Error("timeout"));
		await mount("/lead");
		await settle();
		fake.lists[0].data = [{ name: "LEAD-1" }];
		await nextTick();
		expect(page.hasCounts.value).toBe(true);
		expect(page.totalCount.value).toBe(1);
		expect(page.totalCapped.value).toBe(true);
		expect(page.hasNextPage.value).toBe(true);
	});
});

describe("deleteSelection", () => {
	it("deletes each selected name, reports a failure, clears the selection and reloads", async () => {
		await mount("/lead");
		await settle();
		fake.remove.mockResolvedValueOnce("ok").mockRejectedValueOnce(new Error("Not permitted"));
		page.selection.value = ["LEAD-1", "LEAD-2"];
		const outcome = await page.deleteSelection();
		expect(fake.remove.mock.calls.map(([params]) => params)).toEqual([{ name: "LEAD-1" }, { name: "LEAD-2" }]);
		expect(outcome).toEqual({ deleted: ["LEAD-1"], failed: [{ name: "LEAD-2", error: "Not permitted" }] });
		expect(page.selection.value).toEqual([]);
		expect(fake.useList).toHaveBeenCalledTimes(2);
	});
});
