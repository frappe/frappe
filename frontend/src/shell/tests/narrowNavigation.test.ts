// The navigation from 768 to 1023 px: the overlay sidebar (rail_overlay) and the drawer.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { acts } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem, NavigationLayout } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { installTranslate } from "@/i18n";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { canPin, navigationLayout, pinned } from "../navigationLayout";
import { navigationSide } from "../navigationSide";

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"], "Sales Order": ["sales-order", "accounts"] },
	modules: { accounts: "Accounts" },
});
const stub = { render: () => null };

const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const docs: NavigationItem = { key: "docs", item_type: "Link", label: "Docs", url: "https://docs.frappe.io" };
const sidebars = {
	module_def_accounts: [
		{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" },
		{ key: "order", item_type: "DocType", link_to: "Sales Order" },
	],
};

const mounted: App[] = [];
let router: Router;

async function flush() {
	for (let tick = 0; tick < 4; tick++) await Promise.resolve();
	await nextTick();
	await nextTick();
}

function device(width: number) {
	Object.defineProperty(window, "innerWidth", { value: width, configurable: true });
	window.matchMedia = ((query: string) => {
		const min = /min-width:\s*(\d+)px/.exec(query);
		const matches = min ? width >= Number(min[1]) : query.includes("any-hover");
		return {
			matches,
			media: query,
			addEventListener: () => {},
			removeEventListener: () => {},
			addListener: () => {},
			removeListener: () => {},
		} as unknown as MediaQueryList;
	}) as typeof window.matchMedia;
}

function navigation(layout: NavigationLayout): Navigation {
	return { rail: [accounts, docs], sidebars, navigation_layout: layout };
}

async function shell(layout: NavigationLayout, side = "", path = "/sales-invoice"): Promise<HTMLElement> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: navigation(layout),
		session: {
			user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com", navigation_side: side },
			defaults: {},
		},
	} as unknown as Boot;
	router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:doctype", name: "list", component: stub }],
	});
	registerShell({ boot, addresses, router });
	const host = document.body.appendChild(document.createElement("div"));
	const app = createApp(defineComponent({ render: () => h(AppShell) }));
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	installTranslate(app);
	await router.push(path);
	await router.isReady();
	app.mount(host);
	mounted.push(app);
	await flush();
	return host;
}

const q = <T extends HTMLElement = HTMLElement>(selector: string) => document.body.querySelector<T>(selector);
const menu = () => q("[data-key='open-navigation']");
const drawer = () => q("[data-navigation-drawer]");
const scrim = () => q("[data-sidebar-scrim]");
const panel = () => q("[data-slot='sidebar']");
const shellRoot = () => q("[data-slot='desktop-shell']")!;
const press = (key: string) => window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));

beforeAll(async () => {
	registerStandardPages(standardPages);
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	localStorage.clear();
	resetNavigationReports();
	resetSprite();
	navigationSide.value = "start";
	navigationLayout.value = "rail_and_sidebar";
	pinned.value = false;
	canPin.value = false;
	device(820);
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	vi.restoreAllMocks();
});

describe("rail + sidebar at 820 px (rail_overlay)", () => {
	it("draws the rail, the sidebar over the page behind a scrim, and no menu button", async () => {
		await shell("rail_and_sidebar");
		expect(menu()).toBeNull();
		expect(q("[data-slot='sidebar-rail']")).not.toBeNull();
		expect(shellRoot().style.getPropertyValue("--shell-header-inset-start")).toBe("0px");
		expect(panel()?.getAttribute("data-state")).toBe("collapsed");
		expect(scrim()).toBeNull();
		// The sidebar token is transparent in dark mode: the overlay brings its own ground.
		expect(panel()?.parentElement?.classList.contains("bg-surface-base")).toBe(true);
	});

	it("opens from the toggle act over a scrim, leaves collapsed-sidebar alone, and a scrim click closes it", async () => {
		await shell("rail_and_sidebar");
		localStorage.setItem("collapsed-sidebar", "true");
		await acts.run("shell.toggle_sidebar");
		await flush();
		expect(panel()?.getAttribute("data-state")).toBe("expanded");
		expect(scrim()).not.toBeNull();
		expect(localStorage.getItem("collapsed-sidebar")).toBe("true");
		scrim()!.click();
		await flush();
		expect(panel()?.getAttribute("data-state")).toBe("collapsed");
		expect(scrim()).toBeNull();
	});

	it("Escape and a navigation close it", async () => {
		await shell("rail_and_sidebar");
		await acts.run("shell.toggle_sidebar");
		await flush();
		press("Escape");
		await flush();
		expect(panel()?.getAttribute("data-state")).toBe("collapsed");
		await acts.run("shell.toggle_sidebar");
		await flush();
		await router.push("/sales-order");
		await flush();
		expect(panel()?.getAttribute("data-state")).toBe("collapsed");
	});
});

describe("the drawer at 820 px", () => {
	it.each<[NavigationLayout]>([["sidebar_only"], ["floating_rail"]])("%s: a menu button, the header inset, no rail", async (layout) => {
		await shell(layout);
		expect(menu()).not.toBeNull();
		expect(shellRoot().style.getPropertyValue("--shell-header-inset-start")).toBe("2.25rem");
		expect(q("[data-slot='sidebar-rail']")).toBeNull();
		expect(drawer()).toBeNull();
	});

	it("the menu button opens the drawer with the rail and the sidebar, and no pin control", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		expect(drawer()).not.toBeNull();
		expect(drawer()!.querySelector("[data-slot='sidebar-rail']")).not.toBeNull();
		expect(drawer()!.querySelector("[data-slot='sidebar']")).not.toBeNull();
		expect(drawer()!.querySelector("[data-key='pin-navigation'], [data-key='unpin-navigation']")).toBeNull();
	});

	it("the sidebar-only layout holds the sidebar-only list", async () => {
		await shell("sidebar_only");
		menu()!.click();
		await flush();
		expect(drawer()!.querySelector("[data-slot='sidebar-rail']")).toBeNull();
		expect(drawer()!.textContent).toContain("Accounts");
	});

	it("comes in from the navigation's side, and the button sits on it", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		expect(drawer()!.className).toContain("left-0");
		expect(menu()!.parentElement!.className).toContain("left-5");
		mounted.splice(0).forEach((app) => app.unmount());
		document.body.innerHTML = "";
		navigationSide.value = "end";
		await shell("floating_rail", "end");
		menu()!.click();
		await flush();
		expect(drawer()!.className).toContain("right-0");
		expect(drawer()!.className).toContain("flex-row-reverse");
		expect(menu()!.parentElement!.className).toContain("right-5");
	});

	it("Escape and the scrim close it", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		press("Escape");
		await vi.waitFor(() => expect(drawer()).toBeNull());
		menu()!.click();
		await flush();
		q("[data-navigation-drawer-scrim]")!.click();
		await vi.waitFor(() => expect(drawer()).toBeNull());
	});

	it("a navigation closes it", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		await router.push("/sales-order");
		await vi.waitFor(() => expect(drawer()).toBeNull());
	});

	it("a row click closes it", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		drawer()!.querySelector<HTMLElement>("[data-slot='sidebar-item']")!.click();
		await vi.waitFor(() => expect(drawer()).toBeNull());
	});

	it("a rail cell that opens a sidebar only browses: the drawer stays through its navigation", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		const cell = drawer()!.querySelector<HTMLElement>("[data-sidebar] [data-slot='sidebar-rail-item']")!;
		expect(cell).not.toBeNull();
		cell.click();
		await router.push("/sales-order");
		await flush();
		expect(drawer()).not.toBeNull();
	});

	it("Tab wraps inside the drawer", async () => {
		await shell("floating_rail");
		menu()!.click();
		await flush();
		const nodes = [...drawer()!.querySelectorAll<HTMLElement>(
			'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
		)];
		nodes[nodes.length - 1].focus();
		const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
		nodes[nodes.length - 1].dispatchEvent(tab);
		expect(tab.defaultPrevented).toBe(true);
		expect(document.activeElement).toBe(nodes[0]);
		const back = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
		nodes[0].dispatchEvent(back);
		expect(document.activeElement).toBe(nodes[nodes.length - 1]);
	});

	it("is not drawn at 1024 px: the floating rail takes over, and at 767 px the phone draws nothing here", async () => {
		device(1024);
		await shell("floating_rail");
		expect(menu()).toBeNull();
		mounted.splice(0).forEach((app) => app.unmount());
		document.body.innerHTML = "";
		device(767);
		await shell("floating_rail");
		expect(menu()).toBeNull();
	});
});
