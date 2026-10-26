// The router opens the registered standard pages, and a declared replacement wins over them.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import type { StandardPages } from "@/contributions/types";
import MainPage from "@/pages/MainPage.vue";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";

vi.mock("virtual:frappe/contributions", () => ({
	default: {
		doctypes: [],
		pages: [],
		itemTypes: [],
		replacements: [
			{
				app: "erpnext",
				doctype: "Sales Invoice",
				key: "list",
				foreign: false,
				component: async () => page("declared list"),
			},
		],
	},
}));

const registered: StandardPages = {
	main: MainPage,
	home: async () => page("registered home"),
	module: async () => page("registered module"),
	list: async () => page("registered list"),
	record: async () => page("registered record"),
	newRecord: async () => page("registered new record"),
};

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Purchase Invoice": ["purchase-invoice", "accounts"],
	},
	modules: { accounts: "Accounts" },
	singles: [],
});

const boot = {
	app: "erpnext",
	shell_base: "/apps/erpnext",
	prefixes: { erpnext: { app: "erpnext", modular: true } },
} as unknown as Boot;

const apps: ReturnType<typeof createApp>[] = [];

beforeAll(() => {
	registerContributions(["frappe", "erpnext"]);
	registerStandardPages(registered);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

describe("the standard pages", () => {
	it.each([
		["/", "registered home"],
		["/accounts", "registered module"],
		["/accounts/purchase-invoice", "registered list"],
		["/accounts/purchase-invoice/PI-001", "registered record"],
		["/accounts/purchase-invoice/new", "registered new record"],
		["/accounts/sales-invoice/view/list", "registered list"],
		["/accounts/sales-invoice/SI-001", "registered record"],
	])("open the registered page at %s", async (path, expected) => {
		expect(await shownAt(path)).toBe(expected);
	});

	it("give way to a declared page at the main address", async () => {
		expect(await shownAt("/accounts/sales-invoice")).toBe("declared list");
	});
});

function page(name: string) {
	return defineComponent({ render: () => h("div", { "data-page": name }) });
}

async function shownAt(path: string) {
	const router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	await router.push(path);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(RouterView) }));
	app.use(router);
	app.provide("addresses", addresses);
	app.mount(root);
	apps.push(app);
	for (let turn = 0; turn < 5; turn++) {
		await nextTick();
		await new Promise((resolve) => setTimeout(resolve));
	}
	return root.querySelector<HTMLElement>("[data-page]")?.dataset.page;
}
