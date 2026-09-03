// Which row the address is standing on.
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
	path: string,
	prefer: string[] = []
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
		path,
		prefer
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
		// A record has no row of its own, so the list it belongs to is the answer.
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
		// And so shows no panel: falling back would be storing a selection.
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
		// One address really can sit in two places. The tie-break is reading order: the rail top
		// to bottom, and a linked item's panel where the item sits. Accounts is above Deals here.
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
		// A sidebar that resolved to nothing is left out of the payload, and its rail item is
		// drawn as independent, which here means not at all.
		expect(at(rail, { module_def_accounts: [] }, "/sales-invoice")).toEqual({});
	});
});

// Many destinations sit in more than one panel; `Item` sits in six on ERPNext.
describe("the panel the reader is already in", () => {
	// Two panels both listing Sales Invoice, Buying above Stock. Rail order answers Buying.
	const rail: NavigationItem[] = [
		{ key: "buying", item_type: "Sidebar", link_to: "module_def_buying" },
		{ key: "stock", item_type: "Sidebar", link_to: "module_def_stock" },
	];
	const sidebars = {
		module_def_buying: [invoice],
		module_def_stock: [{ ...invoice, key: "invoice-in-stock" }],
	};

	it("takes the first in rail order on a cold load, with nothing to prefer", () => {
		expect(at(rail, sidebars, "/sales-invoice")).toEqual({
			railKey: "buying",
			sidebar: "module_def_buying",
			rowKey: "invoice",
		});
	});

	it("keeps the reader in the panel they are already in", () => {
		expect(at(rail, sidebars, "/sales-invoice", ["module_def_stock"])).toEqual({
			railKey: "stock",
			sidebar: "module_def_stock",
			rowKey: "invoice-in-stock",
		});
	});

	it("takes the earliest preference, so the open panel beats what the tab remembers", () => {
		// So walking into an address you once read elsewhere does not teleport you.
		expect(
			at(rail, sidebars, "/sales-invoice", ["module_def_stock", "module_def_buying"])
				.sidebar
		).toBe("module_def_stock");
	});

	it("never beats a deeper cover", () => {
		// The pinned row in Buying covers the record more deeply than Stock's list.
		const pinned: NavigationItem = {
			key: "pinned",
			item_type: "Record",
			link_doctype: "Sales Invoice",
			link_to: "SI-001",
		};
		const deeper = { ...sidebars, module_def_buying: [invoice, pinned] };

		expect(
			at(rail, deeper, "/sales-invoice/SI-001", ["module_def_stock"])
		).toEqual({
			railKey: "buying",
			sidebar: "module_def_buying",
			rowKey: "pinned",
		});
	});

	it("ignores a preference no panel here answers to", () => {
		// The whole of `?sidebar=` validation: an unknown name is not among the covers, so it
		// loses and the canonical panel answers.
		expect(at(rail, sidebars, "/sales-invoice", ["module_def_nowhere"]).sidebar).toBe(
			"module_def_buying"
		);
	});

	it("cannot conjure a panel for an address nothing covers", () => {
		expect(at(rail, sidebars, "/crm-deal", ["module_def_stock"])).toEqual({});
	});
});

describe("one panel listing a destination twice", () => {
	// Neither app ships this yet, but both expect to add one.
	const rail: NavigationItem[] = [
		{ key: "stock", item_type: "Sidebar", link_to: "module_def_stock" },
	];

	it("highlights the first row going down the panel", () => {
		// The likely case is a pinned row above a categorised copy, where reading order
		// highlights the pinned one.
		const sidebars = {
			module_def_stock: [
				{ ...invoice, key: "pinned-invoice" },
				{ ...invoice, key: "filed-invoice" },
			],
		};
		expect(at(rail, sidebars, "/sales-invoice").rowKey).toBe("pinned-invoice");
	});
});
