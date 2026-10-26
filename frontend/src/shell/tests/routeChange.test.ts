// What the shell draws again on a route change: only what the new address changes.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type ComponentPublicInstance } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { itemRenderers, registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		Supplier: ["supplier", "buying"],
		Item: ["item", "stock"],
		Note: ["note", "desk"],
	},
	modules: { accounts: "Accounts", buying: "Buying", stock: "Stock", desk: "Desk" },
});

const rail: NavigationItem[] = [
	{ key: "accounts", item_type: "Sidebar", link_to: "module_def_accounts", label: "Accounts" },
	{ key: "buying", item_type: "Sidebar", link_to: "module_def_buying", label: "Buying" },
	{ key: "stock", item_type: "Sidebar", link_to: "module_def_stock", label: "Stock" },
	{ key: "note", item_type: "DocType", link_to: "Note" },
];
const sidebars: Record<string, NavigationItem[]> = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
	module_def_buying: [{ key: "supplier", item_type: "DocType", link_to: "Supplier" }],
	module_def_stock: [{ key: "item", item_type: "DocType", link_to: "Item" }],
};

const page = { render: () => h("div", { "data-page": "" }) };

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** The shell on `/sales-invoice`, counting each component's redraws by its name. */
async function shell(): Promise<{ router: Router; redraws: Map<string, number> }> {
	const boot = {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular: false } },
		navigation: { rail, sidebars },
		session: {
			user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com" },
		},
	} as unknown as Boot;

	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: page },
			{ path: "/:doctype", name: "list", component: page },
			{ path: "/:doctype/:name", name: "record", component: page },
		],
	});
	registerShell({ boot, addresses, router });

	const redraws = new Map<string, number>();
	const app = createApp(AppShell);
	app.mixin({
		beforeUpdate(this: ComponentPublicInstance) {
			const name = this.$.type.__name ?? this.$.type.name ?? "";
			redraws.set(name, (redraws.get(name) ?? 0) + 1);
		},
	});
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);

	await router.push("/sales-invoice");
	await router.isReady();
	const host = document.createElement("div");
	document.body.appendChild(host);
	app.mount(host);
	await settle();
	redraws.clear();

	return { router, redraws };
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	resetNavigationReports();
	resetSprite();
	vi.restoreAllMocks();
});

describe("a route change", () => {
	it("does not draw the rail or sidebar items again", async () => {
		const { router } = await shell();
		const renders = vi.spyOn(itemRenderers.DocType, "render");

		await router.push("/sales-invoice/SI-001");
		await settle();
		await router.push("/sales-invoice");
		await settle();

		expect(renders).not.toHaveBeenCalled();
	});

	it("draws only the rows of a sidebar it opens", async () => {
		const { router } = await shell();
		const renders = vi.spyOn(itemRenderers.DocType, "render");

		await router.push("/supplier");
		await settle();

		expect(renders.mock.calls.map(([item]) => item.key)).toEqual(["supplier"]);
	});

	it("draws again only the rail cells whose current state changed", async () => {
		const { router, redraws } = await shell();

		await router.push("/supplier");
		await settle();

		// Accounts stops being current and Buying starts; Stock and Note stay as they were.
		expect(redraws.get("SidebarRailItem")).toBe(2);
	});

	it("draws nothing in the rail or the open sidebar inside the same sidebar", async () => {
		const { router, redraws } = await shell();

		await router.push("/sales-invoice/SI-001");
		await settle();

		expect(redraws.get("RailColumn")).toBeUndefined();
		expect(redraws.get("SidebarRailItem")).toBeUndefined();
		expect(redraws.get("SidebarRow")).toBeUndefined();
	});
});
