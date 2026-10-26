// An app's and a module's bare address redirect to their landing: the first row navigation
// resolves to a route in the prefix. With none, the address stays and shows nothing to open.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import { RouterView } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import NothingToOpen from "@/shell/NothingToOpen.vue";

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		Account: ["account", "accounts"],
		"Sales Invoice": ["sales-invoice", "accounts"],
		Item: ["item", "stock"],
		"Quality Goal": ["quality-goal", "quality-management"],
	},
	modules: {
		accounts: "Accounts",
		stock: "Stock",
		"quality-management": "Quality Management",
	},
	singles: [],
});

const link: NavigationItem = { key: "docs", item_type: "Link", url: "https://example.com" };
const section: NavigationItem = { key: "masters", item_type: "Section", label: "Masters" };
const contents: NavigationItem = {
	key: "more",
	item_type: "Module Contents",
	link_to: "Accounts",
};
const doctype = (name: string): NavigationItem => ({
	key: name,
	item_type: "DocType",
	link_to: name,
});
const sidebar = (address: string): NavigationItem => ({
	key: address,
	item_type: "Sidebar",
	link_to: address,
});
const moduleItem = (name: string): NavigationItem => ({
	key: name,
	item_type: "Module",
	link_to: name,
});

const apps: ReturnType<typeof createApp>[] = [];

beforeAll(() => {
	registerContributions(["frappe"]);
	registerStandardPages(standardPages);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function erpnext(navigation?: Navigation): Boot {
	return {
		app: "erpnext",
		app_title: "ERPNext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular: true } },
		navigation,
	} as unknown as Boot;
}

function routerFor(boot: Boot) {
	const router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	return router;
}

async function mount(boot: Boot, router: ReturnType<typeof routerFor>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({ render: () => h(RouterView) });
	app.use(router).provide("boot", boot);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return root;
}

describe("an app's bare address", () => {
	it("lands on the first rail item that resolves to a route, through a sidebar", async () => {
		const router = routerFor(
			erpnext({
				rail: [link, section, contents, sidebar("module_def_stock")],
				sidebars: { module_def_stock: [section, doctype("Item")] },
			})
		);

		await router.push("/");

		expect(router.currentRoute.value.fullPath).toBe("/stock/item?sidebar=module_def_stock");
	});

	it("lands through a module item onto that module's sidebar", async () => {
		const router = routerFor(
			erpnext({
				rail: [moduleItem("Accounts")],
				sidebars: { module_def_accounts: [doctype("Account")] },
			})
		);

		await router.push("/");

		expect(router.currentRoute.value.fullPath).toBe(
			"/accounts/account?sidebar=module_def_accounts"
		);
	});

	it("stays and shows nothing to open when no rail item resolves", async () => {
		const boot = erpnext({ rail: [link, section], sidebars: {} });
		const router = routerFor(boot);

		await router.push("/");
		const root = await mount(boot, router);

		expect(router.currentRoute.value.name).toBe("home");
		const state = root.querySelector('[data-page-state="nothingToOpen"]');
		expect(state?.textContent).toContain("Nothing in ERPNext you can open");
		expect(state?.querySelector("button")?.textContent?.trim()).toBe("All apps");
	});

	it("does not enter history, so Back returns to where the person came from", async () => {
		const router = routerFor(erpnext({ rail: [doctype("Sales Invoice")], sidebars: {} }));
		await router.push("/accounts/account");
		const entries = window.history.length;

		await router.push("/");

		expect(router.currentRoute.value.fullPath).toBe("/accounts/sales-invoice");
		expect(window.history.length).toBe(entries + 1);
		expect(window.history.state.back).toBe("/accounts/account");
	});
});

describe("a module's bare address", () => {
	it("lands on the first row of the module's own sidebar", async () => {
		const router = routerFor(
			erpnext({
				rail: [sidebar("module_def_stock")],
				sidebars: {
					module_def_stock: [doctype("Item")],
					module_def_quality_management: [section, link, doctype("Quality Goal")],
				},
			})
		);

		await router.push("/quality-management");

		expect(router.currentRoute.value.fullPath).toBe(
			"/quality-management/quality-goal?sidebar=module_def_quality_management"
		);
	});

	it("skips a row that leads to another landing", async () => {
		const router = routerFor(
			erpnext({
				rail: [],
				sidebars: {
					module_def_accounts: [
						moduleItem("Accounts"),
						moduleItem("Stock"),
						doctype("Account"),
					],
				},
			})
		);

		await router.push("/accounts");

		expect(router.currentRoute.value.fullPath).toBe(
			"/accounts/account?sidebar=module_def_accounts"
		);
	});

	it("stays and shows nothing to open when the module has no sidebar", async () => {
		const router = routerFor(
			erpnext({ rail: [doctype("Item")], sidebars: { module_def_stock: [doctype("Item")] } })
		);

		await router.push("/accounts");

		expect(router.currentRoute.value.name).toBe("module");
		expect(router.currentRoute.value.matched[0].components?.default).toBe(NothingToOpen);
	});
});

describe("the index", () => {
	it("keeps its own page at its bare address", async () => {
		const router = routerFor({
			app: null,
			shell_base: "/apps",
			prefixes: {},
		} as unknown as Boot);

		await router.push("/");

		expect(router.currentRoute.value.name).toBe("home");
		expect(router.currentRoute.value.matched[0].components?.default).not.toBe(NothingToOpen);
	});
});
