// Which row the address is standing on (#42421).
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "@/navigation/context";
import { coverage, currentNavigation } from "@/navigation/current";
import { registerContributions } from "@/contributions/registry";

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { fcrm: "FCRM", accounts: "Accounts" },
});

const boot = {
	app: "crm",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
} as unknown as Boot;

const stub = { render: () => null };
const router = createRouter({
	history: createMemoryHistory(),
	routes: [
		{ path: "/", name: "home", component: stub },
		{ path: "/:doctype", name: "list", component: stub },
		{ path: "/:doctype/view/:viewName", name: "saved-view", component: stub },
		{ path: "/:doctype/:name", name: "record", component: stub },
	],
});
registerShell({ boot, addresses, router });

await registerContributions(["frappe"]);

function at(
	rail: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>,
	path: string
) {
	const compose = (items: NavigationItem[]) =>
		itemContext(boot, addresses, router, items, sidebars);

	return currentNavigation(
		rail,
		sidebars,
		{
			rail: compose(rail),
			sidebars: Object.fromEntries(
				Object.entries(sidebars).map(([address, rows]) => [address, compose(rows)])
			),
		},
		path
	);
}

const deal: NavigationItem = { key: "deal", item_type: "DocType", link_to: "CRM Deal" };
const invoice: NavigationItem = {
	key: "invoice",
	item_type: "DocType",
	link_to: "Sales Invoice",
};

describe("coverage", () => {
	it("counts the segments a row covers", () => {
		expect(coverage("/crm-deal/CRM-DEAL-01", "/crm-deal")).toBe(1);
		expect(coverage("/crm-deal", "/crm-deal")).toBe(1);
		expect(coverage("/crm-deal", "/")).toBe(0);
	});

	it("does not read one name as a prefix of another", () => {
		// `startsWith` would put `/crm-deals` under `/crm-deal`, which is a different doctype.
		expect(coverage("/crm-deals", "/crm-deal")).toBe(-1);
	});

	it("does not cover what is shallower than the row", () => {
		expect(coverage("/crm-deal", "/crm-deal/CRM-DEAL-01")).toBe(-1);
	});
});

describe("the rail alone", () => {
	it("marks the row whose list you are on", () => {
		expect(at([deal, invoice], {}, "/sales-invoice")).toEqual({ railKey: "invoice" });
	});

	it("keeps the list marked while you read one of its records", () => {
		// A record has no row of its own and never will — a rail cannot list 553 doctypes'
		// records — so the list it belongs to is the honest answer.
		expect(at([deal, invoice], {}, "/crm-deal/CRM-DEAL-01")).toEqual({ railKey: "deal" });
	});

	it("prefers the deeper of two rows that both cover the address", () => {
		// A pinned record sits under the list it belongs to, so both rows cover its address and
		// `router-link-active` would light both. The deeper one is where you are.
		const pinned: NavigationItem = {
			key: "pinned",
			item_type: "Record",
			link_doctype: "CRM Deal",
			link_to: "CRM-DEAL-01",
		};
		expect(at([deal, pinned], {}, "/crm-deal/CRM-DEAL-01")).toEqual({ railKey: "pinned" });
		// And order does not rescue the shallower one: coverage is compared first.
		expect(at([pinned, deal], {}, "/crm-deal/CRM-DEAL-01")).toEqual({ railKey: "pinned" });
	});

	it("never marks a row that leaves the prefix", () => {
		const link: NavigationItem = {
			key: "docs",
			item_type: "Link",
			url: "https://docs.frappe.io",
		};
		expect(at([link], {}, "/crm-deal")).toEqual({});
	});

	it("marks nothing when no row covers the address", () => {
		// And so shows no panel. There is no last panel to fall back to, because falling back
		// is storing a selection (charter point 7).
		expect(at([deal], {}, "/sales-invoice")).toEqual({});
	});
});

describe("a rail item that opens a sidebar", () => {
	const rail: NavigationItem[] = [
		{ key: "accounts", item_type: "Sidebar", link_to: "module_def_accounts" },
		deal,
	];
	const sidebars = { module_def_accounts: [invoice, { ...deal, key: "in-accounts" }] };

	it("is marked from any row inside its sidebar, not only the first", () => {
		// Its own destination is the sidebar's FIRST row, so `router-link-active` would go out
		// the moment you moved to the second one.
		expect(at(rail, sidebars, "/sales-invoice")).toEqual({
			railKey: "accounts",
			sidebar: "module_def_accounts",
			rowKey: "invoice",
		});
	});

	it("competes through its sidebar's rows rather than through its own destination", () => {
		// Counting both would let the linked item beat the panel it opens, on the one row they
		// share, and the panel would open with nothing marked in it.
		expect(at(rail, sidebars, "/sales-invoice").rowKey).toBe("invoice");
	});

	it("wins a tie against a later rail row on the same doctype", () => {
		// Sidebars link outside their own module all the time — #42357 counted 101 rows doing
		// it in ERPNext — so one address really can sit in two places. The tie-break is the
		// order the person is looking at: the rail top to bottom, and a linked item's panel
		// where the item sits. Accounts is above Deals here and contains it.
		expect(at(rail, sidebars, "/crm-deal")).toEqual({
			railKey: "accounts",
			sidebar: "module_def_accounts",
			rowKey: "in-accounts",
		});
	});

	it("loses that tie when the plain row is above it", () => {
		expect(at([deal, ...rail.slice(0, 1)], sidebars, "/crm-deal")).toEqual({
			railKey: "deal",
		});
	});

	it("is absent when its sidebar has no rows", () => {
		// #42356 leaves a sidebar that resolved to nothing out of the payload, and the renderer
		// then draws the rail item as an independent one — which here means not at all.
		expect(at(rail, { module_def_accounts: [] }, "/sales-invoice")).toEqual({});
	});
});
