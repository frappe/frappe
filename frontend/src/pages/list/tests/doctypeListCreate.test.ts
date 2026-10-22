// The list page's Create button: shown with the create right, opened with the list's filter
// values, and a saved record reloads the rows and says so.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const page = vi.hoisted(() => ({
	reload: vi.fn(),
	createValues: {} as Record<string, unknown>,
}));
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));

function stub(name: string) {
	return defineComponent({ setup: () => () => h("div", { [`data-stub-${name}`]: "" }) });
}

vi.mock("frappe-ui", async (original) => ({ ...(await original<typeof import("frappe-ui")>()), toast }));
vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent } = await import("vue");
	return {
		default: defineComponent({
			setup: (_, { slots }) => () => [slots.header?.(), slots.default?.()],
		}),
		pageGutter: "",
	};
});
vi.mock("@framework/ui/QuickFilter", () => ({ QuickFilter: stub("quick-filter") }));
vi.mock("@framework/ui/Filter", () => ({ Filter: stub("filter") }));
vi.mock("@framework/ui/SortBy", () => ({ SortBy: stub("sort") }));
vi.mock("@framework/ui/ColumnSettings", () => ({ ColumnSettings: stub("columns") }));
vi.mock("@framework/ui/experimental/List", () => ({
	List: stub("list"),
	ListBulkBar: stub("bulk-bar"),
	ListFooter: stub("footer"),
}));
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async () => {
	const { computed, ref } = await import("vue");
	return {
		useListPage: () => {
			const empty = () => ref([]);
			return {
				filters: empty(),
				sort: empty(),
				columns: empty(),
				quickFilterFields: ref(undefined),
				customizing: ref(false),
				selection: empty(),
				pageSize: ref(20),
				rowsKey: () => "",
				rows: empty(),
				loading: ref(false),
				error: ref(null),
				metaError: ref(null),
				seeded: ref(true),
				rowCount: ref(0),
				totalCount: ref(0),
				totalCapped: ref(false),
				totalUnknown: ref(false),
				hasCounts: ref(false),
				hasNextPage: ref(false),
				createValues: computed(() => page.createValues),
				reload: page.reload,
			};
		},
	};
});

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { closeCreates, createRequests, registerCreateDialog } from "@/shell/create";
import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import DoctypeList from "../DoctypeList.vue";

const fetchMock = vi.fn<typeof fetch>();
const addresses = new Addresses({ doctypes: { Contact: ["contact", "crm"] }, modules: { crm: "CRM" } });

const SESSION: Session = {
	user: { name: "test@example.com", full_name: "Test", email: "test@example.com", user_image: null, document_follow_notify: false },
	roles: ["Sales User", "Desk User"],
	lang: "en",
	timezone: "Asia/Kolkata",
	defaults: {},
};

let meta: Record<string, unknown>;
let boot: Boot;
let router: Router;
const apps: App[] = [];

function contactMeta(permissions: Record<string, unknown>[]) {
	return { name: "Contact", fields: [{ fieldname: "first_name", fieldtype: "Data", label: "First Name" }], permissions };
}

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	setSession(SESSION);
	registerCreateDialog(stub("create-dialog"));
	closeCreates();
	toast.success.mockReset();
	page.reload.mockReset();
	page.createValues = {};
	meta = contactMeta([{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }]);
	boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		read_only_mode: false,
	} as unknown as Boot;
	fetchMock.mockReset().mockImplementation(async (url) => {
		const path = new URL(String(url), "http://x").pathname;
		if (path === "/api/v2/doctype/Contact/meta") return new Response(JSON.stringify({ data: meta }));
		return new Response(JSON.stringify({ errors: [{ type: "NotFound", message: path }] }), { status: 404 });
	});
	vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	closeCreates();
	resetSession();
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function mount() {
	router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/:name", name: "record", component: { render: () => null } },
		],
	});
	registerShell({ boot, addresses, router });
	await router.push("/contact");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(DoctypeList, { doctype: "Contact" }) }));
	app.use(router).provide("addresses", addresses).provide("boot", boot);
	app.mount(root);
	apps.push(app);
	await settle();
	return root;
}

function createButton(root: HTMLElement) {
	return [...root.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Create");
}

async function clickCreate(root: HTMLElement) {
	createButton(root)!.click();
	await settle();
}

describe("DoctypeList Create button", () => {
	it("shows for a person whose role may create the doctype", async () => {
		const root = await mount();
		expect(createButton(root)).toBeTruthy();
	});

	it("is hidden when no role of the person's may create", async () => {
		meta = contactMeta([
			{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 0 },
			{ role: "Sales Manager", permlevel: 0, read: 1, create: 1 },
		]);
		const root = await mount();
		expect(createButton(root)).toBeUndefined();
	});

	it("is hidden in read-only mode", async () => {
		boot = { ...boot, read_only_mode: true } as Boot;
		const root = await mount();
		expect(createButton(root)).toBeUndefined();
	});

	it("is hidden for a doctype that takes no new records from a list", async () => {
		meta = { ...meta, in_create: 1 };
		const root = await mount();
		expect(createButton(root)).toBeUndefined();
	});

	it("opens Create for the doctype with the list's filter values", async () => {
		page.createValues = { status: "Open", company: "Acme" };
		const root = await mount();

		await clickCreate(root);

		expect(createRequests.value).toHaveLength(1);
		expect(createRequests.value[0]).toMatchObject({
			doctype: "Contact",
			values: { status: "Open", company: "Acme" },
		});
	});

	it("reloads the rows and shows a toast that opens the saved record", async () => {
		const root = await mount();
		await clickCreate(root);

		createRequests.value[0].settle({ name: "CONT-0001" });
		await settle();

		expect(page.reload).toHaveBeenCalledOnce();
		expect(toast.success).toHaveBeenCalledOnce();
		const [message, options] = toast.success.mock.calls[0];
		expect(message).toBe("Contact CONT-0001 created");
		expect(options.action.label).toBe("Open");

		options.action.onClick();
		await settle();
		expect(router.currentRoute.value.path).toBe("/contact/CONT-0001");
	});

	it("opens one Create for a double click, and another once the first is answered", async () => {
		const root = await mount();
		await clickCreate(root);
		await clickCreate(root);
		expect(createRequests.value).toHaveLength(1);

		createRequests.value[0].settle(null);
		createRequests.value[0].dismiss();
		await settle();
		await clickCreate(root);
		expect(createRequests.value).toHaveLength(1);
	});

	it("does nothing when the Create is dismissed", async () => {
		const root = await mount();
		await clickCreate(root);

		createRequests.value[0].settle(null);
		await settle();

		expect(page.reload).not.toHaveBeenCalled();
		expect(toast.success).not.toHaveBeenCalled();
		expect(router.currentRoute.value.path).toBe("/contact");
	});
});
