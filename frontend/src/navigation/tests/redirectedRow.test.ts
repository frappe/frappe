// A row typed with a spelling the router redirects still marks, and opens, its own sidebar.
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { canonicalPath } from "@/navigation/canonical";
import { itemContext } from "@/navigation/context";
import { currentFrom, navigationDestinations } from "@/navigation/current";
import { registerContributions } from "@/contributions/registry";

const addresses = new Addresses({
	doctypes: { Currency: ["currency", "geo"], "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { geo: "Geo", accounts: "Accounts" },
});

const boot = {
	app: "erpnext",
	shell_base: "/apps/erpnext",
	prefixes: { erpnext: { app: "erpnext", modular: true } },
} as unknown as Boot;

const stub = { render: () => null };
const router = createRouter({
	history: createMemoryHistory(),
	routes: [
		{ path: "/", name: "home", component: stub },
		{ path: "/:module", name: "module", component: stub },
		{ path: "/:module/:doctype", name: "list", component: stub },
		{ path: "/:module/:doctype/:name", name: "record", component: stub },
	],
});
registerShell({ boot, addresses, router });

await registerContributions(["frappe"]);

describe("canonicalPath", () => {
	const of = (to: string) => canonicalPath(router, addresses, to);

	it("moves a doctype to its own module", () => {
		expect(of("/accounts/currency")).toBe("/geo/currency");
	});

	it("reads a flat address through the modular table", () => {
		expect(of("/currency")).toBe("/geo/currency");
	});

	it("leaves a canonical address alone", () => {
		expect(of("/geo/currency")).toBe("/geo/currency");
	});

	it("keeps the query out of the path", () => {
		expect(of("/accounts/currency?sidebar=mine")).toBe("/geo/currency");
	});

	it("leaves an address that is no doctype's alone", () => {
		expect(of("/geo/unknown")).toBe("/geo/unknown");
	});
});

describe("an own row to a redirected route", () => {
	const link = (key: string, path: string): NavigationItem => ({
		key,
		item_type: "Link",
		url: `/apps/erpnext${path}`,
	});

	it("opens its own sidebar, which the address asked for, over a sidebar holding the canonical row", () => {
		const rail = [
			{ ...link("mine", "/accounts/currency"), opens_sidebar: "mine-side" },
			{ key: "accounts", item_type: "Sidebar", link_to: "accounts-side" } as NavigationItem,
		];
		const sidebars = {
			"mine-side": [link("copy", "/accounts/currency")],
			"accounts-side": [link("currency", "/geo/currency")],
		};
		const compose = (items: NavigationItem[]) =>
			itemContext(boot, addresses, router, items, sidebars);
		const contexts = {
			rail: compose(rail),
			sidebars: Object.fromEntries(
				Object.entries(sidebars).map(([address, rows]) => [address, compose(rows)])
			),
		};

		const destinations = navigationDestinations(rail, sidebars, contexts);
		const found = currentFrom(destinations, "/geo/currency", ["mine-side"]);

		expect(found.sidebar).toBe("mine-side");
		expect(found.railKey).toBe("mine");
	});
});
