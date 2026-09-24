// The shell's error page for a page that fails to load, in place of the routed view.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import {
	createMemoryHistory,
	createRouter,
	isNavigationFailure,
	NavigationFailureType,
	type Router,
} from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { failedPage, resetFailedPage, trackFailedPages } from "@/router/failedPage";
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

// Set by a test: the slow page's import, and whether the flaky page's guard throws.
const slow = { load: new Promise<never>(() => {}) };
const flaky = { fails: false };

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

function makeRouter() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			{
				path: "/broken",
				name: "broken",
				component: () => Promise.reject(new Error("the chunk failed to load")),
			},
			{ path: "/slow", name: "slow", component: () => slow.load },
			{
				path: "/throws",
				name: "throws",
				component: { render: () => null },
				beforeEnter: () => {
					throw new Error("the guard failed");
				},
			},
			{
				path: "/refused",
				name: "refused",
				component: { render: () => null },
				beforeEnter: () => false,
			},
			{
				path: "/flaky",
				name: "flaky",
				component: { render: () => null },
				beforeEnter: () => {
					if (flaky.fails) throw new Error("the guard failed on return");
				},
			},
			{
				path: "/:doctype",
				name: "list",
				component: { render: () => h("div", { "data-page": "list" }) },
			},
		],
	});
	trackFailedPages(router);
	return router;
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
	resetFailedPage();
	resetNavigationReports();
	resetSprite();
	flaky.fails = false;
	window.history.replaceState(null, "", "/");
	vi.restoreAllMocks();
});

describe("a page that fails to load", () => {
	it("shows the error page in place of the page, inside the rail and the sidebar", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await expect(router.push("/broken")).rejects.toThrow("the chunk failed to load");
		await settle();

		expect(text(host)).toContain("This page could not load.");
		expect(host.querySelector("main [role='alert']")).not.toBeNull();
		expect(host.querySelector("[data-page]")).toBeNull();
		expect(host.querySelector("nav[aria-label='crm']")).not.toBeNull();
		expect(host.querySelector("[data-slot='sidebar'] nav[aria-label='Accounts']")).not.toBeNull();
	});

	it("opens the failed address from Try again", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const reload = vi.spyOn(window.location, "reload").mockImplementation(() => {});

		await router.push("/broken").catch(() => {});
		await settle();
		tryAgain(host);

		expect(assign).toHaveBeenCalledWith("/broken");
		expect(reload).not.toHaveBeenCalled();
	});

	it("reloads from Try again when the failed address, hash and all, is the one loaded", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const reload = vi.spyOn(window.location, "reload").mockImplementation(() => {});
		window.history.replaceState(null, "", "/broken#details");

		await router.push("/broken#details").catch(() => {});
		await settle();
		tryAgain(host);

		expect(reload).toHaveBeenCalledOnce();
		expect(assign).not.toHaveBeenCalled();
	});

	it("shows the page again when the reader goes back to it", async () => {
		const { host, router } = await shell();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push("/broken").catch(() => {});
		await settle();
		await router.push("/sales-invoice");
		await settle();

		expect(text(host)).not.toContain("This page could not load.");
		expect(host.querySelector("[data-page='list']")).not.toBeNull();
	});
});

describe("the failed address", () => {
	async function started() {
		const router = makeRouter();
		await router.push("/sales-invoice");
		return router;
	}

	it("is set by an error thrown in a guard", async () => {
		const router = await started();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await expect(router.push("/throws")).rejects.toThrow("the guard failed");

		expect(failedPage.value).toBe("/throws");
	});

	it("stays when a later navigation is refused by a guard", async () => {
		const router = await started();
		vi.spyOn(console, "error").mockImplementation(() => {});

		await router.push("/broken").catch(() => {});
		const refused = await router.push("/refused");

		expect(isNavigationFailure(refused, NavigationFailureType.aborted)).toBe(true);
		expect(failedPage.value).toBe("/broken");
	});

	it("is set by a failure on the way back", async () => {
		const router = await started();
		vi.spyOn(console, "error").mockImplementation(() => {});
		await router.push("/flaky");
		await router.push("/purchase-invoice");

		flaky.fails = true;
		router.back();
		await settle();

		expect(failedPage.value).toBe("/flaky");
		expect(router.currentRoute.value.path).toBe("/purchase-invoice");
	});

	it("ignores a failure of a navigation a newer one has replaced", async () => {
		const router = await started();
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		let fail!: (reason: Error) => void;
		slow.load = new Promise<never>((_resolve, reject) => (fail = reject));

		const abandoned = router.push("/slow").catch(() => {});
		await settle();
		await router.push("/purchase-invoice");
		fail(new Error("the slow page failed to load"));
		await abandoned;
		await settle();

		expect(error).toHaveBeenCalledWith(
			expect.objectContaining({ message: "the slow page failed to load" })
		);
		expect(failedPage.value).toBeNull();
		expect(router.currentRoute.value.path).toBe("/purchase-invoice");
	});
});
