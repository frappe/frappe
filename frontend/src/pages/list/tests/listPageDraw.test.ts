// The list page draws what the page engine holds: the header row, the frame's bands and the body's
// columns, so a list.js edit to `page.header`, `page.frame` or `page.body` shows.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const hooks = vi.hoisted(() => ({ refresh: undefined as undefined | ((page: any) => void) }));
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));

function stub(name: string) {
	return defineComponent({ setup: () => () => h("div", { [`data-stub-${name}`]: "" }) });
}

vi.mock("frappe-ui", async (original) => ({ ...(await original<typeof import("frappe-ui")>()), toast }));
vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		default: defineComponent({
			setup: (_, { slots }) => () => [slots.aboveHeader?.(), h("header", slots.header?.()), slots.default?.()],
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
vi.mock("@/list/useListPage", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/list/useListPage")>()),
	useListPage: (await import("./fakeListPage")).useListPage,
}));
vi.mock("@/list/useListView", async () => ({
	useListView: (await import("./fakeListPage")).useListView,
}));

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { closeCreates, createRequests, registerCreateDialog } from "@/shell/create";
import { addListScript } from "@/contributions/registry";
import type { ListPageApi } from "@/listPage/types";
import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/useSession";
import { PLAIN_LIST } from "@/list/useListPage";
import ViewPage from "../ViewPage.vue";
import { fake, installListRenderer, resetFake } from "./fakeListPage";

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
	return { name: "Contact", module: "Contacts", fields: [{ fieldname: "first_name", fieldtype: "Data", label: "First Name" }], permissions };
}

// The loader keeps a doctype's scripts for the session: one script, and each test sets what it does.
addListScript("Contact", {
	app: "test",
	load: async () => ({ default: { onRefresh: (page: ListPageApi) => hooks.refresh?.(page) } }),
});

beforeEach(async () => {
	hooks.refresh = undefined;
	resetFake();
	await installListRenderer();
	resetDoctypeMeta();
	clearDataCache();
	setSession(SESSION);
	registerCreateDialog(stub("create-dialog"));
	closeCreates();
	toast.success.mockReset();
	meta = contactMeta([{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }]);
	boot = {
		app: "crm",
		session: { user: { name: "Administrator" } },
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

async function mount(label = "") {
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
	const app = createApp(defineComponent({ render: () => h(ViewPage, { doctype: "Contact", opened: label ? { ...PLAIN_LIST, key: "mine", label, layer: "user" } : PLAIN_LIST }) }));
	app.use(router).provide("addresses", addresses).provide("boot", boot);
	app.mount(root);
	apps.push(app);
	await settle();
	return root;
}


const crumbs = (root: HTMLElement) =>
	[...root.querySelectorAll("header [data-crumbs] a, header [data-crumbs] span")].map((one) =>
		one.textContent?.trim()
	);
const button = (root: HTMLElement, label: string) =>
	root.querySelector<HTMLButtonElement>(`header button[aria-label='${label}']`);
const createButton = (root: HTMLElement) =>
	[...root.querySelectorAll("header button")].find((one) => one.textContent?.trim() === "Create");

describe("the list page header", () => {
	it("draws the module crumb, then the doctype crumb, and Create on the right", async () => {
		const root = await mount();
		expect(root.querySelector("header [data-crumbs]")?.textContent).toMatch(/Contacts.*Contact/);
		expect(createButton(root)).toBeTruthy();
		expect(button(root, "More actions")).toBeNull();
	});

	it("draws the saved view's name after the doctype, which then links to the list", async () => {
		const root = await mount("My Contacts");
		const links = [...root.querySelectorAll<HTMLAnchorElement>("header [data-crumbs] a")];
		expect(links.map((link) => link.getAttribute("href"))).toContain("/contact");
		expect(root.querySelector("header [data-crumbs]")?.textContent).toMatch(/Contact.*My Contacts/);
	});

	it("draws the ⋯ menu once a script adds an entry to it", async () => {
		hooks.refresh = (page) => page.header.add({ name: "export", label: "Export", run: vi.fn() });
		const root = await mount();
		expect(button(root, "More actions")).not.toBeNull();
	});

	it("draws a script's button and runs it with the page", async () => {
		const run = vi.fn();
		hooks.refresh = (page) =>
			page.header.add({ name: "sync", label: "Sync", display: "button", run }, { before: "new" });
		const root = await mount();
		button(root, "Sync")!.click();
		await settle();
		expect(run).toHaveBeenCalledTimes(1);
		expect(run.mock.calls[0][0]).toMatchObject({ doctype: "Contact" });
	});

	it("keeps Create in the row, whatever buttons a script adds", async () => {
		hooks.refresh = (page) => {
			for (const name of ["a", "b", "c"])
				page.header.add({ name, label: name.toUpperCase(), display: "button", run: vi.fn() }, { before: "new" });
		};
		const root = await mount();
		expect(createButton(root)).toBeTruthy();
		expect(button(root, "More actions")).not.toBeNull();
	});

	it("is the script's to hide: Create goes, and the row with it when nothing else is left", async () => {
		hooks.refresh = (page) => {
			page.header.clear();
			page.header.add({ name: "note", label: "Note", display: "button", run: vi.fn() });
		};
		const root = await mount();
		expect(createButton(root)).toBeUndefined();
		expect(button(root, "Note")).not.toBeNull();
	});

	it("draws no row when the frame hides the header", async () => {
		hooks.refresh = (page) => page.frame.hide("header");
		const root = await mount();
		expect(root.querySelector("header")!.children).toHaveLength(0);
		expect(root.querySelector("[data-stub-filter]")).not.toBeNull();
	});
});

describe("the list page frame and body", () => {
	it("draws a script's bands around the header and after the body", async () => {
		hooks.refresh = (page) => {
			page.frame.add({ name: "top", component: stub("top") }, { before: "header" });
			page.frame.add({ name: "middle", component: stub("middle") }, { after: "header" });
			page.frame.add({ name: "bottom", component: stub("bottom") }, { after: "body" });
		};
		const root = await mount();
		const order = [...root.querySelectorAll("[data-frame-band], header, [data-body-column=list]")].map(
			(one) => (one as HTMLElement).dataset.frameBand ?? one.tagName.toLowerCase() + ((one as HTMLElement).dataset.bodyColumn ?? "")
		);
		expect(order).toEqual(["top", "header", "middle", "divlist", "bottom"]);
	});

	it("draws the controls and the rows in the body's list column", async () => {
		const root = await mount();
		const column = root.querySelector("[data-body-column=list]")!;
		expect(column.querySelector("[data-stub-filter]")).not.toBeNull();
		expect(column.querySelector("[data-stub-list]")).not.toBeNull();
	});

	it("draws a script's column beside the list, and none when the body is hidden", async () => {
		hooks.refresh = (page) => page.body.add({ name: "side", component: stub("side"), width: 280 });
		let root = await mount();
		expect(root.querySelector("[data-body-column=side] [data-stub-side]")).not.toBeNull();
		expect(root.querySelector("[data-body-column=list]")).not.toBeNull();

		for (const app of apps.splice(0)) app.unmount();
		document.body.innerHTML = "";
		hooks.refresh = (page) => page.frame.hide("body");
		root = await mount();
		expect(root.querySelector("[data-body-column]")).toBeNull();
	});
});
