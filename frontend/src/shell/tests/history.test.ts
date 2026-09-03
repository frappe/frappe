// Which sidebar a page is read in, as the reader walks back and forward (#42480).
//
// `createWebHistory`, not the memory history the other shell tests use: the sidebar is
// stamped on the history entry, and only a real one carries state through a pop.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createRouter, createWebHistory, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";

const fetchContents = vi.hoisted(() => vi.fn());
vi.mock("@/contents", () => ({ fetchContents }));

const addresses = new Addresses({
	doctypes: {
		Item: ["item", "stock"],
		"Stock Entry": ["stock-entry", "stock"],
		Supplier: ["supplier", "buying"],
		Note: ["note", "desk"],
	},
	modules: { stock: "Stock", buying: "Buying", desk: "Desk" },
});

const stub = { render: () => null };

// `Item` sits in both sidebars, which is what makes the address alone unable to answer
// which one a page was read in.
const rail: NavigationItem[] = [
	{ key: "stock", item_type: "Sidebar", link_to: "module_def_stock", label: "Stock" },
	{ key: "buying", item_type: "Sidebar", link_to: "module_def_buying", label: "Buying" },
	// Independent, and in no sidebar: following it leaves nothing open, which is the one
	// case the address-keyed record still answers.
	{ key: "note", item_type: "DocType", link_to: "Note" },
];
const sidebars: Record<string, NavigationItem[]> = {
	module_def_stock: [
		{ key: "item", item_type: "DocType", link_to: "Item" },
		{ key: "entry", item_type: "DocType", link_to: "Stock Entry" },
	],
	module_def_buying: [
		{ key: "item", item_type: "DocType", link_to: "Item" },
		{ key: "supplier", item_type: "DocType", link_to: "Supplier" },
	],
};

async function flush() {
	await Promise.resolve();
	await nextTick();
}

/** A pop and the `replace` that strips the parameter both land a task later. */
async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await flush();
	}
}

function makeRouter() {
	return createRouter({
		history: createWebHistory("/"),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
			{ path: "/:doctype/view/:viewName", name: "saved-view", component: stub },
			{ path: "/:doctype/:name", name: "record", component: stub },
		],
	});
}

/** The shell, mounted at `path` over the window's own history. */
async function shell(path: string): Promise<{ host: HTMLElement; router: Router; app: App }> {
	const boot = {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular: false } },
		navigation: { rail, sidebars },
		user: { name: "reader@example.com", full_name: "Reader" },
	} as unknown as Boot;

	const router = makeRouter();
	registerShell({ boot, addresses, router });

	const host = document.createElement("div");
	document.body.appendChild(host);

	const app = createApp(AppShell);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);

	await router.push(path);
	await router.isReady();
	app.mount(host);
	await settle();

	return { host, router, app };
}

/** The sidebar open now, read off the rail row the shell marks current. */
function open(host: HTMLElement): string | null | undefined {
	const marked = host.querySelector("nav [aria-current='page']");
	return marked?.getAttribute("data-sidebar");
}

/** Follow a row the way a reader does: the href it drew, pushed. */
async function follow(host: HTMLElement, router: Router, key: string) {
	const link = host.querySelector<HTMLAnchorElement>(`[data-key='${key}']`);
	await router.push(link!.getAttribute("href")!);
	await settle();
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(async () => {
	document.body.innerHTML = "";
	sessionStorage.clear();
	// One window across a file's tests, so the stack a previous walk left behind is cleared
	// back to a single entry.
	window.history.replaceState(null, "", "/");
	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
});

/** Steps 1-5 of #42479's walk: `Item` read in Stock, then `Item` read in Buying. */
async function walk() {
	const { host, router, app } = await shell("/stock-entry?sidebar=module_def_stock");
	const panel = () => host.querySelector("aside")!;

	await follow(panel(), router, "item");
	await follow(host.querySelector("nav")!, router, "buying");

	return { host, router, app };
}

describe("the sidebar a page was read in", () => {
	it("opens the one the address names", async () => {
		const { host } = await shell("/stock-entry?sidebar=module_def_stock");
		expect(open(host)).toBe("module_def_stock");
	});

	it("stays open as the reader follows a row inside it", async () => {
		const { host, router } = await walk();
		expect(open(host)).toBe("module_def_buying");
		expect(router.currentRoute.value.fullPath).toBe("/item");
	});

	it("comes back with the reader", async () => {
		const { host, router } = await walk();

		router.go(-1);
		await settle();
		// The same address, and the sidebar it was READ in rather than the one open a moment
		// ago, which is the whole fix.
		expect(router.currentRoute.value.path).toBe("/item");
		expect(open(host)).toBe("module_def_stock");

		router.go(-1);
		await settle();
		expect(router.currentRoute.value.path).toBe("/stock-entry");
		expect(open(host)).toBe("module_def_stock");
	});

	it("goes forward with the reader too", async () => {
		const { host, router } = await walk();

		router.go(-1);
		await settle();
		router.go(-1);
		await settle();

		router.go(1);
		await settle();
		expect(open(host)).toBe("module_def_stock");

		router.go(1);
		await settle();
		expect(router.currentRoute.value.path).toBe("/item");
		expect(open(host)).toBe("module_def_buying");
	});

	it("survives a reload, on every entry and not only the current one", async () => {
		const { app } = await walk();
		app.unmount();
		document.body.innerHTML = "";

		// A fresh shell over the same window: the stamps are on the entries, not in anything
		// the old one was holding.
		const reloaded = await shell(window.location.pathname);
		expect(open(reloaded.host)).toBe("module_def_buying");

		reloaded.router.go(-1);
		await settle();
		expect(open(reloaded.host)).toBe("module_def_stock");
	});
});

describe("what the address-keyed record is left holding", () => {
	function recorded() {
		return JSON.parse(sessionStorage.getItem("frappe:desk:sidebar") ?? "{}");
	}

	it("records the sidebar a push resolved", async () => {
		await walk();
		expect(recorded()).toEqual({
			"/stock-entry": "module_def_stock",
			"/item": "module_def_buying",
		});
	});

	it("is not rewritten by a back", async () => {
		const { router } = await walk();

		router.go(-1);
		await settle();
		// The reader is standing in Stock, and the record still says what the last push said.
		expect(recorded()["/item"]).toBe("module_def_buying");
	});

	it("answers a push arriving from an independent rail item", async () => {
		const { host, router } = await walk();

		await follow(host.querySelector("nav")!, router, "note");
		expect(open(host)).toBe(null);

		// A fresh entry, so no stamp, and nothing open to carry: the record is all there is.
		await router.push("/item");
		await settle();
		expect(open(host)).toBe("module_def_buying");
	});
});

describe("the parameter the address carries", () => {
	it("outranks the stamp, because a paste is deliberate", async () => {
		const { host, router } = await walk();

		router.go(-1);
		await settle();
		expect(open(host)).toBe("module_def_stock");

		await router.push("/item?sidebar=module_def_buying");
		await settle();
		expect(open(host)).toBe("module_def_buying");
	});

	it("is consumed once, leaving the hash where it was", async () => {
		const { host, router } = await shell("/item?sidebar=module_def_stock#notes");
		expect(open(host)).toBe("module_def_stock");
		expect(router.currentRoute.value.fullPath).toBe("/item#notes");
	});

	it("is read and stripped when the address repeats it", async () => {
		const { host, router } = await shell(
			"/item?sidebar=module_def_stock&sidebar=module_def_buying"
		);
		expect(open(host)).toBe("module_def_stock");
		expect(router.currentRoute.value.fullPath).toBe("/item");
	});

	it("loses to the address when it names a sidebar nothing here answers to", async () => {
		const { host } = await shell("/supplier?sidebar=module_def_nowhere");
		expect(open(host)).toBe("module_def_buying");
	});
});
