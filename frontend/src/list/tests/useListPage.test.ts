// The composable as claims: what seeds it, what it writes to the URL, when it rebuilds the list,
// and what a delete does. frappe-ui's data layer is faked; the router and history are real.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick, reactive, type App } from "vue";
import { createRouter, createWebHistory, type Router } from "vue-router";

const fake = vi.hoisted(() => ({
	meta: null as Record<string, unknown> | null,
	contributed: [] as { columns?: { fieldname: string; width?: number }[] }[],
	lists: [] as any[],
	useList: vi.fn(),
	call: vi.fn(),
	remove: vi.fn(),
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<object>()),
	call: fake.call,
	useList: fake.useList,
	createResource: () => ({
		get data() {
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
import { forgetRows, readListMemory, recallRows, writeListMemory } from "../pageState";
import { useListPage, type ListPage } from "../useListPage";

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

/** A changed query waits out the typing debounce before it builds a list. */
async function settleQuery() {
	await new Promise((resolve) => setTimeout(resolve, 350));
	await settle();
}

beforeEach(() => {
	resetDoctypeMeta();
	forgetRows("Lead");
	history.replaceState(null, "");
	fake.meta = { name: "Lead", title_field: "title", sort_field: "amount", sort_order: "ASC", fields: FIELDS };
	fake.contributed = [];
	fake.lists = [];
	fake.useList.mockReset().mockImplementation(fakeList);
	fake.call.mockReset().mockResolvedValue(42);
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
