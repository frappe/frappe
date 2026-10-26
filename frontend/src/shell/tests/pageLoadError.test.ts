// The shell's error page for a page that fails to load, in place of the routed view.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { clearLoadedPages, loadedPage } from "@/router/mainPage";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { accounts: "Accounts" },
});

const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

function makeRouter() {
	return createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			{
				path: "/:doctype",
				name: "list",
				component: { render: () => h("div", { "data-page": "list" }) },
			},
			{
				path: "/:doctype/:name",
				name: "record",
				component: loadedPage(() => Promise.reject(new Error("the chunk failed to load"))),
			},
		],
	});
}

/** The shell, mounted on `/sales-invoice` with the Accounts panel open. */
async function shell(): Promise<{ host: HTMLElement; router: Router }> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: { rail: [accounts], sidebars },
		session: {
			user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com" },
		},
	} as unknown as Boot;

	const router = makeRouter();
	registerShell({ boot, addresses, router });

	const host = document.createElement("div");
	document.body.appendChild(host);

	const app = createApp(AppShell);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);

	await router.push("/sales-invoice");
	await router.isReady();
	app.mount(host);
	await settle();

	return { host, router };
}

function text(host: HTMLElement) {
	return host.querySelector("main")?.textContent ?? "";
}

function tryAgain(host: HTMLElement) {
	const retry = [...host.querySelectorAll("button")].find(
		(button) => button.textContent?.trim() === "Try again"
	);
	retry!.click();
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	clearLoadedPages();
	resetNavigationReports();
	resetSprite();
	window.history.replaceState(null, "", "/");
	vi.restoreAllMocks();
});

describe("a page that fails to load", () => {
	it("shows the error page in place of the page, inside the rail and the sidebar", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push("/sales-invoice/SI-001");
		await settle();

		expect(router.currentRoute.value.path).toBe("/sales-invoice/SI-001");
		expect(text(host)).toContain("This page could not load.");
		expect(host.querySelector("main [role='alert']")).not.toBeNull();
		expect(host.querySelector("[data-page]")).toBeNull();
		expect(host.querySelector("nav[aria-label='crm']")).not.toBeNull();
		expect(host.querySelector("[data-slot='sidebar'] nav[aria-label='Accounts']")).not.toBeNull();
	});

	it("reloads the address from Try again", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});
		const reload = vi.spyOn(window.location, "reload").mockImplementation(() => {});

		await router.push("/sales-invoice/SI-001");
		await settle();
		tryAgain(host);

		expect(reload).toHaveBeenCalledOnce();
	});

	it("shows the page again when the reader goes back to it", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push("/sales-invoice/SI-001");
		await settle();
		await router.push("/sales-invoice");
		await settle();

		expect(text(host)).not.toContain("This page could not load.");
		expect(host.querySelector("[data-page='list']")).not.toBeNull();
	});
});
