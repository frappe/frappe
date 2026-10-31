// A doctype's bare address opens its default view from boot, as a landing does; a query or a
// longer address keeps its own page.
import { describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";

registerContributions(["frappe"]);
registerStandardPages(standardPages);

vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		Account: ["account", "accounts"],
	},
	modules: { accounts: "Accounts" },
	singles: [],
});

describe.each([
	{ shape: "flat", modular: false, prefix: "" },
	{ shape: "modular", modular: true, prefix: "/accounts" },
])("the default view on a $shape app", ({ modular, prefix }) => {
	function routerFor(default_views: Record<string, string>, navigation?: Boot["navigation"]) {
		const boot = {
			app: "erpnext",
			shell_base: "/apps/erpnext",
			prefixes: { erpnext: { app: "erpnext", modular } },
			default_views,
			navigation,
		} as unknown as Boot;
		const router = createShellRouter(boot, addresses);
		registerShell({ boot, addresses, router });
		return router;
	}

	it("replaces the bare address with the default's, with no history entry of its own", async () => {
		const router = routerFor({ "Sales Invoice": "open-invoices" });
		await router.push(`${prefix}/account`);
		const entries = window.history.length;

		await router.push(`${prefix}/sales-invoice#settings`);

		const route = router.currentRoute.value;
		expect(route.name).toBe("saved-view");
		expect(route.fullPath).toBe(`${prefix}/sales-invoice/view/open-invoices#settings`);
		expect(window.history.length).toBe(entries + 1);
		expect(window.history.state.back).toBe(`${prefix}/account`);
	});

	it("opens a plain view default at /view/<type>, the type's standard page", async () => {
		const router = routerFor({ "Sales Invoice": "list" });

		await router.push(`${prefix}/sales-invoice`);

		expect(router.currentRoute.value.name).toBe("standard-list");
		expect(router.currentRoute.value.path).toBe(`${prefix}/sales-invoice/view/list`);
	});

	it("keeps a bare address that carries a query on the plain list", async () => {
		const router = routerFor({ "Sales Invoice": "open-invoices" });

		await router.push(`${prefix}/sales-invoice?status=Paid`);

		expect(router.currentRoute.value.name).toBe("list");
		expect(router.currentRoute.value.fullPath).toBe(`${prefix}/sales-invoice?status=Paid`);
	});

	it("keeps /view/<type> and another saved view where they are", async () => {
		const router = routerFor({ "Sales Invoice": "open-invoices" });

		await router.push(`${prefix}/sales-invoice/view/list`);
		expect(router.currentRoute.value.name).toBe("standard-list");

		await router.push(`${prefix}/sales-invoice/view/overdue`);
		expect(router.currentRoute.value.params.key).toBe("overdue");
	});

	it("leaves a doctype with no default, and a record, on their own pages", async () => {
		const router = routerFor({ "Sales Invoice": "open-invoices" });

		await router.push(`${prefix}/account`);
		expect(router.currentRoute.value.name).toBe("list");

		await router.push(`${prefix}/sales-invoice/SINV-0001`);
		expect(router.currentRoute.value.name).toBe("record");
	});

	it("opens the default after the slug is put right", async () => {
		const router = routerFor({ "Sales Invoice": "open-invoices" });

		await router.push(`${prefix}/Sales Invoice`);

		expect(router.currentRoute.value.path).toBe(`${prefix}/sales-invoice/view/open-invoices`);
	});

	it("opens the default of the doctype an app's address lands on", async () => {
		const router = routerFor(
			{ "Sales Invoice": "open-invoices" },
			{ rail: [{ key: "si", item_type: "DocType", link_to: "Sales Invoice" }], sidebars: {} }
		);

		await router.push("/");

		expect(router.currentRoute.value.path).toBe(`${prefix}/sales-invoice/view/open-invoices`);
	});
});
