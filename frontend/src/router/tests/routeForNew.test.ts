// The full-page new record and the values it carries in its query.
import { describe, expect, it, vi } from "vitest";
import type { RouteLocationRaw } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { createShellRouter } from "@/router";
import { registerShell, routeForNew } from "@/router/routeFor";

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/NewRecord.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Selling Settings": ["selling-settings", "selling"],
	},
	modules: { accounts: "Accounts", selling: "Selling" },
	singles: ["Selling Settings"],
});

function shell(modular: boolean) {
	const boot = {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular } },
	} as unknown as Boot;
	const router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	return router;
}

function queryOf(route: RouteLocationRaw) {
	return (route as { query?: Record<string, string> }).query;
}

describe("routeForNew", () => {
	it("is the new-record route, with no query for no values", () => {
		const router = shell(false);

		expect(routeForNew("Sales Invoice")).toEqual({
			name: "new-record",
			params: { doctype: "sales-invoice" },
			query: {},
		});
		expect(router.resolve(routeForNew("Sales Invoice")).fullPath).toBe("/sales-invoice/new");
	});

	it("opens a single's one record, whatever values were given", () => {
		const router = shell(false);

		const route = routeForNew("Selling Settings", { customer_group: "All" });

		expect(router.resolve(route).fullPath).toBe("/selling-settings/Selling%20Settings");
	});

	it("leaves a saved record named new at its standard address", () => {
		const router = shell(false);

		expect(router.resolve("/sales-invoice/new").name).toBe("new-record");
		expect(router.resolve("/sales-invoice/new/record").name).toBe("standard-record");
		expect(router.resolve("/sales-invoice/new/record").params.name).toBe("new");
	});

	it("sends an old flat new-record link under a modular prefix to the new-record route", async () => {
		const router = shell(true);

		await router.push("/sales-invoice/new?customer=Acme");

		expect(router.currentRoute.value.name).toBe("new-record");
		expect(router.currentRoute.value.fullPath).toBe("/accounts/sales-invoice/new?customer=Acme");
	});

	it("puts each value in the query as text, and a table or object as JSON", () => {
		shell(false);
		const items = [{ item_code: "PEN", qty: 2 }];

		const route = routeForNew("Sales Invoice", {
			customer: "Acme",
			is_return: 1,
			grand_total: 12.5,
			paid: false,
			items,
			address: { city: "Pune" },
		});

		expect(queryOf(route)).toEqual({
			customer: "Acme",
			is_return: "1",
			grand_total: "12.5",
			paid: "false",
			items: JSON.stringify(items),
			address: JSON.stringify({ city: "Pune" }),
		});
	});

	it("drops a null, undefined or empty value", () => {
		shell(false);

		const route = routeForNew("Sales Invoice", {
			customer: "Acme",
			company: null,
			project: undefined,
			remarks: "",
			discount: 0,
		});

		expect(queryOf(route)).toEqual({ customer: "Acme", discount: "0" });
	});

	it("stays inside a modular prefix, with the doctype's module", () => {
		const router = shell(true);

		const route = routeForNew("Sales Invoice", { customer: "Acme" });

		expect(router.resolve(route).fullPath).toBe("/accounts/sales-invoice/new?customer=Acme");
	});
});
