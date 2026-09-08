// The overlay host: the customize dialog addressed by the hash, and the helper under it.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";
import { useHashDialog } from "../useHashDialog";

// The dialog loads its list when the hash names one; an empty list is enough to prove it opened.
vi.mock("@/arrangement", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/arrangement")>()),
	fetchArrangement: vi.fn().mockResolvedValue([]),
}));

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { accounts: "Accounts" },
});

const stub = { render: () => null };

const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

async function flush() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

/** A hash write and a pop both land a task later. */
async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await flush();
	}
}

function makeRouter() {
	return createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
		],
	});
}

/** The shell, mounted at `path`, with the Accounts panel open on `/sales-invoice`. */
async function shell(path: string): Promise<{ host: HTMLElement; router: Router }> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: { rail: [accounts], sidebars },
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
	await flush();

	return { host, router };
}

// The dialog portals to `document.body`, so it is looked for there, never under the host.
function dialog() {
	return document.body.querySelector("[role='dialog']");
}

function list() {
	return document.body.querySelector("[data-testid='customize']");
}

function dialogTitle() {
	return dialog()?.querySelector("h3")?.textContent?.trim();
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	window.history.replaceState(null, "", "/");
	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
});

describe("the dialog, addressed by the hash", () => {
	it("opens the rail's list over the page at #customize/rail", async () => {
		const { host } = await shell("/sales-invoice#customize/rail");

		expect(list()).not.toBeNull();
		expect(dialogTitle()).toBe("Customize sidebar");
		// The page is still under it: the panel the address opens is drawn.
		expect(host.querySelector("[data-slot='sidebar']")).not.toBeNull();
	});

	it("opens a panel's list at #customize/sidebar/<address>", async () => {
		await shell("/sales-invoice#customize/sidebar/module_def_accounts");

		expect(list()).not.toBeNull();
		expect(dialogTitle()).toBe("Customize this sidebar");
	});

	it("opens nothing for a sidebar this prefix does not have", async () => {
		await shell("/sales-invoice#customize/sidebar/module_def_nowhere");
		expect(dialog()).toBeNull();
	});

	it("opens nothing for a hash that is not its own", async () => {
		await shell("/sales-invoice#settings/crm");
		expect(dialog()).toBeNull();
	});

	it("is opened by the panel's own control, and Close drops only the hash", async () => {
		const { host, router } = await shell("/sales-invoice?from=here");

		host.querySelector<HTMLElement>("[aria-label='Customize this sidebar']")!.click();
		await settle();

		expect(router.currentRoute.value.hash).toBe("#customize/sidebar/module_def_accounts");
		expect(list()).not.toBeNull();

		dialog()!.querySelector<HTMLElement>("[aria-label='Close']")!.click();
		await settle();

		expect(router.currentRoute.value.fullPath).toBe("/sales-invoice?from=here");
		expect(dialog()).toBeNull();
	});

	it("is dismissed by Back, because opening it pushed", async () => {
		const { host, router } = await shell("/sales-invoice");

		host.querySelector<HTMLElement>("[aria-label='Customize this sidebar']")!.click();
		await settle();
		expect(list()).not.toBeNull();

		router.go(-1);
		await settle();

		expect(router.currentRoute.value.fullPath).toBe("/sales-invoice");
		expect(dialog()).toBeNull();
	});
});

describe("useHashDialog", () => {
	/** A component that owns one dialog, exposed for the test to drive. */
	async function mount(path: string) {
		const router = makeRouter();
		let dialog!: ReturnType<typeof useHashDialog>;
		const Host = defineComponent({
			setup() {
				dialog = useHashDialog("customize");
				return () => h("div");
			},
		});
		const app = createApp(Host);
		app.use(router);
		await router.push(path);
		await router.isReady();
		app.mount(document.createElement("div"));
		return { router, dialog };
	}

	it("reads its own segments and nothing else's", async () => {
		const own = await mount("/x#customize/sidebar/a");
		expect(own.dialog.open.value).toBe(true);
		expect(own.dialog.segments.value).toEqual(["sidebar", "a"]);

		const foreign = await mount("/x#settings/crm");
		expect(foreign.dialog.open.value).toBe(false);
		expect(foreign.dialog.segments.value).toEqual([]);
	});

	it("pushes to open and replaces to move within, so one Back closes it", async () => {
		const { router, dialog } = await mount("/x?q=1");

		dialog.write("rail");
		await settle();
		dialog.write("sidebar", "a");
		await settle();
		expect(router.currentRoute.value.fullPath).toBe("/x?q=1#customize/sidebar/a");

		router.go(-1);
		await settle();
		expect(router.currentRoute.value.fullPath).toBe("/x?q=1");
	});

	it("closes only its own hash", async () => {
		const own = await mount("/x?q=1#customize/rail");
		own.dialog.close();
		await settle();
		expect(own.router.currentRoute.value.fullPath).toBe("/x?q=1");

		const foreign = await mount("/x#settings/crm");
		foreign.dialog.close();
		await settle();
		expect(foreign.router.currentRoute.value.fullPath).toBe("/x#settings/crm");
	});
});
