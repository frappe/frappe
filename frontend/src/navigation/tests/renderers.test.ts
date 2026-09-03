// The framework's own kinds, through the door an app would use. Nothing is stubbed: the real
// contributions plugin runs over frappe's source, so a misplaced renderer or a name mismatch fails here.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { itemRenderers, registerContributions } from "@/contributions/registry";
import { generatedRoutes } from "@/router/generated";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "../context";
import { renderingOf, labelOf, rendererFor, resetNavigationReports } from "../registry";
import type { ItemContext, ItemRenderer } from "../types";

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { fcrm: "FCRM", accounts: "Accounts" },
});

function boot(overrides: Partial<Boot> = {}): Boot {
	return {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		...overrides,
	} as Boot;
}

let router: Router;

function context(
	items: NavigationItem[],
	overrides: Partial<ItemContext> = {}
): ItemContext {
	const base = itemContext(
		(overrides.boot as Boot) ?? boot(),
		addresses,
		router,
		items,
		overrides.sidebars ?? {}
	);
	return Object.assign(base, overrides);
}

/** A router, because `routeFor` resolves through the one the shell registered. */
function shell(bootValue: Boot) {
	router = createRouter({
		history: createMemoryHistory(),
		routes: [
			...generatedRoutes(!!bootValue.prefixes?.crm?.modular),
			{ path: "/deals", name: "page:crm:deals", component: { render: () => null } },
		],
	});
	registerShell({ boot: bootValue, addresses, router });
	return router;
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	resetNavigationReports();
	shell(boot());
	vi.restoreAllMocks();
});

describe("what the framework ships", () => {
	it("registers a renderer for all eight kinds", () => {
		expect(Object.keys(itemRenderers).sort()).toEqual([
			"DocType",
			"Link",
			"Module",
			"Module Contents",
			"Page",
			"Record",
			"Section",
			"Sidebar",
		]);
	});

	it("names DocType exactly, which title-casing the folder cannot", () => {
		// `doctype` title-cases to "Doctype"; the name is read off the record's own JSON.
		expect(rendererFor("DocType")).toBeDefined();
		expect(rendererFor("Doctype")).toBeUndefined();
	});
});

describe("DocType", () => {
	const item: NavigationItem = {
		key: "CRM Deal",
		item_type: "DocType",
		link_to: "CRM Deal",
	};

	it("goes to the doctype's list", () => {
		expect(renderingOf(item, context([item]))).toEqual({
			to: { name: "list", params: { doctype: "crm-deal" }, query: undefined },
		});
	});

	it("goes one segment deeper under a modular prefix", () => {
		// The trap `routeFor` exists for: a hand-built `/crm-deal` resolves here, to the module route.
		const modular = boot({
			prefixes: { crm: { app: "crm", modular: true } },
		});
		shell(modular);
		expect(renderingOf(item, context([item], { boot: modular }))).toEqual({
			to: {
				name: "list",
				params: { doctype: "crm-deal", module: "fcrm" },
				query: undefined,
			},
		});
	});

	it("falls back to the doctype when nobody labelled it", () => {
		// Which is what every derived rail row is: an address and no authored presentation.
		expect(labelOf(item, context([item]))).toBe("CRM Deal");
	});

	it("renders an authored label literally, never translated", () => {
		expect(labelOf({ ...item, label: "Deals" }, context([item]))).toBe("Deals");
	});
});

describe("Record", () => {
	const item: NavigationItem = {
		key: "starred",
		item_type: "Record",
		link_doctype: "CRM Deal",
		link_to: "CRM-DEAL-01",
	};

	it("carries its own link_doctype, and goes to the document", () => {
		expect(renderingOf(item, context([item]))).toEqual({
			to: {
				name: "record",
				params: { doctype: "crm-deal", name: "CRM-DEAL-01" },
				query: undefined,
			},
		});
	});
});

describe("Module", () => {
	const item: NavigationItem = {
		key: "accounts",
		item_type: "Module",
		link_doctype: "Module Def",
		link_to: "Accounts",
	};

	it("goes to the module page under a modular prefix", () => {
		const modular = boot({ prefixes: { crm: { app: "crm", modular: true } } });
		shell(modular);
		expect(renderingOf(item, context([item], { boot: modular }))).toEqual({
			to: { name: "module", params: { module: "accounts" } },
		});
	});

	it("is not drawn under a non-modular one, which has no module route", () => {
		expect(renderingOf(item, context([item]))).toBeNull();
	});

	it("spells the module with the slug the server sent, never a scrub of its own", () => {
		const modular = boot({ prefixes: { crm: { app: "crm", modular: true } } });
		shell(modular);
		const unknown = { ...item, link_to: "No Such Module" };
		expect(renderingOf(unknown, context([unknown], { boot: modular }))).toBeNull();
	});
});

describe("Link", () => {
	it("is an href and never a route", () => {
		// Its destination is outside this document's router by definition, so following it
		// is a full page load.
		const item: NavigationItem = {
			key: "docs",
			item_type: "Link",
			url: "https://docs.frappe.io",
		};
		expect(renderingOf(item, context([item]))).toEqual({
			href: "https://docs.frappe.io",
		});
	});

	it("is not drawn with no url, since a Link is nothing else", () => {
		const item: NavigationItem = { key: "docs", item_type: "Link" };
		expect(renderingOf(item, context([item]))).toBeNull();
	});
});

describe("Section", () => {
	it("is a group, with no destination of its own", () => {
		const item: NavigationItem = { key: "reports", item_type: "Section" };
		expect(renderingOf(item, context([item]))).toEqual({ group: true });
	});
});

describe("Page", () => {
	const item: NavigationItem = { key: "deals", item_type: "Page", link_to: "deals" };

	it("goes to a page this prefix serves", () => {
		const ctx = context([item], { pages: [{ slug: "deals", title: "Deals" }] });
		expect(renderingOf(item, ctx)).toEqual({ to: { name: "page:crm:deals" } });
	});

	it("takes its label from the page's own title", () => {
		const ctx = context([item], { pages: [{ slug: "deals", title: "Deals" }] });
		expect(labelOf(item, ctx)).toBe("Deals");
	});

	it("is not drawn for a slug this prefix does not serve", () => {
		// The route table holds the DECLARING app's pages only, so a link built for another
		// app's page resolves to the shell's not-found — one hop later, reason lost.
		expect(renderingOf(item, context([item], { pages: [] }))).toBeNull();
	});
});

describe("Module Contents", () => {
	const item: NavigationItem = {
		key: "more",
		item_type: "Module Contents",
		link_doctype: "Module Def",
		link_to: "Accounts",
	};

	it("expands into what the list is not already showing", async () => {
		const shown: NavigationItem = {
			key: "Sales Invoice",
			item_type: "DocType",
			link_to: "Sales Invoice",
		};
		const contentsOf = vi.fn().mockResolvedValue([
			{ doctype: "Sales Invoice", slug: "sales-invoice", module: "accounts" },
			{ doctype: "Journal Entry", slug: "journal-entry", module: "accounts" },
		]);

		const rendering = renderingOf(item, context([item, shown], { contentsOf }));
		expect(rendering).toHaveProperty("expand");

		const rows = await (rendering as { expand: () => Promise<NavigationItem[]> }).expand();
		expect(contentsOf).toHaveBeenCalledWith("accounts");
		expect(rows).toEqual([
			{
				key: "more:Journal Entry",
				item_type: "DocType",
				link_doctype: "DocType",
				link_to: "Journal Entry",
			},
		]);
	});

	it("namespaces the rows it produces under the row that produced them", async () => {
		// A derived rail's keys ARE doctype names (`_derive_rail`), so a bare one would
		// collide with a stored row and take its arrangement.
		const contentsOf = vi
			.fn()
			.mockResolvedValue([{ doctype: "Journal Entry", slug: "je", module: "accounts" }]);
		const rendering = renderingOf(item, context([item], { contentsOf }));
		const rows = await (rendering as { expand: () => Promise<NavigationItem[]> }).expand();
		expect(rows[0].key).toBe("more:Journal Entry");
	});

	it("is not drawn for a module the address table does not know", () => {
		const unknown = { ...item, link_to: "No Such Module" };
		expect(renderingOf(unknown, context([unknown]))).toBeNull();
	});
});

describe("Sidebar", () => {
	const item: NavigationItem = {
		key: "accounts",
		item_type: "Sidebar",
		link_doctype: "Sidebar",
		link_to: "module_def_accounts",
	};

	it("navigates to the first destination inside the sidebar it opens", () => {
		// Selecting a rail item is ordinary navigation, so an address can express it.
		const sidebars = {
			module_def_accounts: [
				{ key: "Sales Invoice", item_type: "DocType", link_to: "Sales Invoice" },
			],
		};
		expect(renderingOf(item, context([item], { sidebars }))).toEqual({
			// The sidebar rides in the link; the shell consumes and strips it on arrival.
			to: {
				name: "list",
				params: { doctype: "sales-invoice" },
				query: { sidebar: "module_def_accounts" },
			},
			sidebar: "module_def_accounts",
		});
	});

	it("skips rows in it that are not destinations", () => {
		const sidebars = {
			module_def_accounts: [
				{ key: "heading", item_type: "Section" },
				{ key: "Sales Invoice", item_type: "DocType", link_to: "Sales Invoice" },
			],
		};
		expect(renderingOf(item, context([item], { sidebars }))).toMatchObject({
			sidebar: "module_def_accounts",
		});
	});

	it("renders as an independent item when its sidebar is absent", () => {
		// An address that resolved to nothing is absent, not empty.
		expect(renderingOf(item, context([item], { sidebars: {} }))).toBeNull();
	});

	it("does not recurse forever on a sidebar that reaches itself", () => {
		const sidebars = { module_def_accounts: [item] };
		expect(renderingOf(item, context([item], { sidebars }))).toBeNull();
	});
});

describe("a kind with no renderer", () => {
	it("is skipped and reported once, not per render", () => {
		const logged = vi.spyOn(console, "error").mockImplementation(() => {});
		const item: NavigationItem = { key: "x", item_type: "Chart" };

		expect(renderingOf(item, context([item]))).toBeNull();
		expect(renderingOf(item, context([item]))).toBeNull();

		expect(logged).toHaveBeenCalledTimes(1);
		expect(logged.mock.calls[0][0]).toContain("Chart");
	});
});

describe("a renderer that throws", () => {
	it("is treated as a missing one: the item is skipped, the rail survives", () => {
		// `routeFor` throws for a doctype the address table has never heard of, which is a
		// real state for a row pointing at an app that has since been uninstalled.
		const logged = vi.spyOn(console, "error").mockImplementation(() => {});
		const item: NavigationItem = {
			key: "gone",
			item_type: "DocType",
			link_to: "Nonexistent Doctype",
		};

		expect(renderingOf(item, context([item]))).toBeNull();
		expect(logged).toHaveBeenCalled();
	});

	it("still draws the item's own label, since naming it is a separate question", () => {
		const item: NavigationItem = {
			key: "gone",
			item_type: "DocType",
			link_to: "Nonexistent Doctype",
		};
		expect(labelOf(item, context([item]))).toBe("Nonexistent Doctype");
	});
});

describe("what a bad renderer cannot do", () => {
	// A contributed renderer is another app's code and must not take the rail down. These are
	// the two ways it could.
	function withRenderer(type: string, renderer: ItemRenderer, run: () => void) {
		itemRenderers[type] = renderer;
		try {
			run();
		} finally {
			delete itemRenderers[type];
		}
	}

	it("cannot blank the rail by naming a route that does not exist", () => {
		// The failure would happen inside `RouterLink` during render, where nothing catches it;
		// checking the route here keeps the promise for a returned value too.
		const logged = vi.spyOn(console, "error").mockImplementation(() => {});
		const item: NavigationItem = { key: "x", item_type: "Widget" };

		withRenderer("Widget", { render: () => ({ to: { name: "no-such-route" } }) }, () => {
			expect(renderingOf(item, context([item]))).toBeNull();
		});

		expect(logged).toHaveBeenCalled();
	});

	it("lets a good route through untouched", () => {
		const item: NavigationItem = { key: "x", item_type: "Widget" };
		const to = { name: "list", params: { doctype: "crm-deal" } };

		withRenderer("Widget", { render: () => ({ to }) }, () => {
			expect(renderingOf(item, context([item]))).toEqual({ to });
		});
	});
});

describe("the recursion guard", () => {
	it("does not confuse two containers' rows that share a key", () => {
		// A `key` identifies a row within one container, so a rail item and a sidebar row may
		// both be called `accounts` without either being a cycle.
		const item: NavigationItem = {
			key: "accounts",
			item_type: "Sidebar",
			link_to: "module_def_accounts",
		};
		const sidebars = {
			module_def_accounts: [
				{ key: "accounts", item_type: "DocType", link_to: "Sales Invoice" },
			],
		};

		expect(renderingOf(item, context([item], { sidebars }))).toEqual({
			// The sidebar rides in the link; the shell consumes and strips it on arrival.
			to: {
				name: "list",
				params: { doctype: "sales-invoice" },
				query: { sidebar: "module_def_accounts" },
			},
			sidebar: "module_def_accounts",
		});
	});
});

describe("off the index, which belongs to no app", () => {
	it("refuses a contents fetch rather than answering that a module is empty", async () => {
		// `[]` is a real answer, so it must not also be what "no app to ask about" looks like.
		const ctx = itemContext(boot({ app: null }), addresses, router, [], {});
		await expect(ctx.contentsOf("accounts")).rejects.toThrow();
	});
});
