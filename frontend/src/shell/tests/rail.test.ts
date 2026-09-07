// What the rail draws. Mounted with Vue's own `createApp`: this package has no `@vue/test-utils`.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type Ref } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { generatedRoutes } from "@/router/generated";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "@/navigation/context";
import { resetNavigationReports } from "@/navigation/registry";
import { loadSprite, resetSprite } from "@/icons/sprite";
import RailColumn from "../RailColumn.vue";

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"CRM Lead": ["crm-lead", "fcrm"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { fcrm: "FCRM", accounts: "Accounts" },
});

const crm = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
} as unknown as Boot;

async function flush() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

type Options = {
	sidebars?: Record<string, NavigationItem[]>;
	current?: string;
	arrangeable?: boolean;
	shareLink?: string;
	boot?: Boot;
};

/** The mounted rail plus the list it renders, so a test can replace it as a save does. */
function mount(
	initial: NavigationItem[],
	options: Options = {}
): { host: HTMLElement; items: Ref<NavigationItem[]>; router: Router } {
	const boot = options.boot ?? crm;
	const items = ref<NavigationItem[]>(initial);
	const host = document.createElement("div");
	document.body.appendChild(host);

	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			...generatedRoutes(false),
		],
	});
	registerShell({ boot, addresses, router });

	// The shell composes the context; the rail is mounted alone here, so this stands in for it.
	const app = createApp({
		render: () =>
			h(RailColumn, {
				items: items.value,
				context: itemContext(boot, addresses, router, items.value, options.sidebars ?? {}),
				current: options.current,
				arrangeable: options.arrangeable,
				shareLink: options.shareLink,
			}),
	});
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	app.mount(host);

	return { host, items, router };
}

function rail(items: NavigationItem[], options: Options = {}) {
	return mount(items, options).host;
}

/** The cell that carries the test hooks; what it wraps is frappe-ui's. */
function cell(host: HTMLElement, key: string) {
	return host.querySelector(`[data-key="${CSS.escape(key)}"]`);
}

/** The link or button inside a cell. */
function target(host: HTMLElement, key: string) {
	return cell(host, key)?.querySelector("[data-slot='rail-item']") ?? null;
}

function marked(host: HTMLElement) {
	return Array.from(host.querySelectorAll("[aria-current='page']")).map((node) =>
		node.closest("[data-key]")?.getAttribute("data-key")
	);
}

function doctype(key: string, parent_key?: string): NavigationItem {
	return { key, item_type: "DocType", link_to: key, ...(parent_key ? { parent_key } : {}) };
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

const SPRITE =
	'<svg id="frappe-symbols" style="display:none">' +
	'<symbol id="icon-users" viewBox="0 0 24 24"><circle cx="9" cy="7" r="4"/></symbol>' +
	"</svg>";

/** The sprite the rail's icons resolve against, loaded the way `main.ts` loads it. */
function withSprite() {
	vi.stubGlobal(
		"fetch",
		vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve(SPRITE) })
	);
	return loadSprite();
}

beforeEach(() => {
	document.body.innerHTML = "";
	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe("the kinds the rail draws", () => {
	it("draws every kind that resolves to a destination", () => {
		const host = rail([
			doctype("CRM Deal"),
			{ key: "docs", item_type: "Link", url: "https://docs.frappe.io" },
			{ key: "invoice", item_type: "Record", link_doctype: "CRM Deal", link_to: "D-1" },
		]);

		expect(cell(host, "CRM Deal")).not.toBeNull();
		expect(cell(host, "docs")).not.toBeNull();
		expect(cell(host, "invoice")).not.toBeNull();
	});

	it("makes a DocType an in-prefix link", () => {
		const host = rail([doctype("CRM Deal")]);
		const link = target(host, "CRM Deal") as HTMLAnchorElement;

		expect(link.tagName).toBe("A");
		expect(link.getAttribute("href")).toBe("/crm-deal");
	});

	it("makes a Link a plain anchor, so middle-click and copy-address survive", () => {
		// A full document load the router cannot resolve, and one `RailItem` cannot draw.
		const host = rail([{ key: "docs", item_type: "Link", url: "https://docs.frappe.io" }]);
		const anchor = target(host, "docs") as HTMLAnchorElement;

		expect(anchor.tagName).toBe("A");
		expect(anchor.getAttribute("href")).toBe("https://docs.frappe.io");
	});
});

describe("headings", () => {
	it("draws a section's children flat and the heading not at all", () => {
		// An icon column has no heading form.
		const host = rail([
			{ key: "sales", item_type: "Section", label: "Sales" },
			doctype("CRM Deal", "sales"),
		]);

		expect(cell(host, "sales")).toBeNull();
		expect(cell(host, "CRM Deal")!.parentElement!.tagName).toBe("NAV");
	});

	it("flattens a third level too", () => {
		const host = rail([
			{ key: "a", item_type: "Section" },
			{ key: "b", item_type: "Section", parent_key: "a" },
			doctype("CRM Deal", "b"),
		]);

		expect(cell(host, "CRM Deal")!.parentElement!.tagName).toBe("NAV");
	});

	it("draws what a keep_closed section holds, since there is no heading to shut", () => {
		const host = rail([
			{ key: "sales", item_type: "Section", collapsible: 1, keep_closed: 1 },
			doctype("CRM Deal", "sales"),
		]);

		expect(cell(host, "CRM Deal")).not.toBeNull();
	});

	it("keeps the children of a heading whose own renderer is missing", () => {
		// The same choice `_promote_orphans` makes on the server: an item that cannot be
		// placed never silently takes what is under it.
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([
			{ key: "mystery", item_type: "Chart", label: "Charts" },
			doctype("CRM Deal", "mystery"),
		]);

		expect(cell(host, "mystery")).toBeNull();
		expect(cell(host, "CRM Deal")).not.toBeNull();
	});
});

describe("a linked item", () => {
	it("carries the sidebar it opens, so the panel can mount off it", () => {
		const host = rail(
			[
				{
					key: "accounts",
					item_type: "Sidebar",
					link_doctype: "Sidebar",
					link_to: "module_def_accounts",
				},
			],
			{
				sidebars: {
					module_def_accounts: [
						{ key: "Sales Invoice", item_type: "DocType", link_to: "Sales Invoice" },
					],
				},
			}
		);

		expect(cell(host, "accounts")!.getAttribute("data-sidebar")).toBe("module_def_accounts");
		// Real navigation, not shell state: the panel is named in the href, so middle-click works.
		expect(target(host, "accounts")!.getAttribute("href")).toBe(
			"/sales-invoice?sidebar=module_def_accounts"
		);
	});

	it("is not drawn when its sidebar is absent", () => {
		const host = rail([
			{ key: "accounts", item_type: "Sidebar", link_to: "module_def_accounts" },
		]);
		expect(cell(host, "accounts")).toBeNull();
	});
});

describe("rows fetched on demand", () => {
	it("are not drawn: an icon column has nowhere to open them", () => {
		const host = rail([
			{
				key: "more",
				item_type: "Module Contents",
				link_doctype: "Module Def",
				link_to: "Accounts",
				label: "More",
			},
			doctype("CRM Deal"),
		]);

		expect(cell(host, "more")).toBeNull();
		expect(cell(host, "CRM Deal")).not.toBeNull();
	});
});

describe("a row that cannot be drawn", () => {
	it("is skipped, and the rest of the rail still renders", () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([{ key: "x", item_type: "Chart" }, doctype("CRM Deal")]);
		expect(cell(host, "x")).toBeNull();
		expect(cell(host, "CRM Deal")).not.toBeNull();
	});

	it("does not blank the rail when a renderer throws", () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([doctype("Nonexistent Doctype"), doctype("CRM Deal")]);
		expect(cell(host, "Nonexistent Doctype")).toBeNull();
		expect(cell(host, "CRM Deal")).not.toBeNull();
	});
});

describe("the current cell", () => {
	it("is the one the shell names, not the one the router matches", async () => {
		// A `Sidebar` item's link resolves to a row inside its panel, so the shell decides.
		const { host, router } = mount([doctype("CRM Deal"), doctype("CRM Lead")], {
			current: "CRM Lead",
		});
		await router.push("/crm-deal");
		await flush();

		expect(marked(host)).toEqual(["CRM Lead"]);
	});
});

describe("the app tile", () => {
	it("shows the app's first letter when boot carries no logo", () => {
		const tile = rail([]).querySelector("[data-key='app-menu']")!;
		expect(tile.textContent?.trim()).toBe("C");
		expect(tile.getAttribute("aria-label")).toBe("CRM menu");
	});

	it("shows the logo when boot carries one", () => {
		const host = rail([], { boot: { ...crm, app_logo: "/assets/crm/logo.svg" } as Boot });
		const image = host.querySelector("[data-key='app-menu'] img");
		expect(image?.getAttribute("src")).toBe("/assets/crm/logo.svg");
	});

	it("reads Apps on the index, which belongs to no app", () => {
		const index = { ...crm, app: null, app_title: undefined } as unknown as Boot;
		const tile = rail([], { boot: index }).querySelector("[data-key='app-menu']")!;
		expect(tile.textContent?.trim()).toBe("A");
	});
});

describe("the app menu", () => {
	/** The menu's text once opened from the keyboard; it renders in a portal on `body`. */
	async function opened(options: Options) {
		document.body.innerHTML = "";
		const host = rail([], options);
		const tile = host.querySelector<HTMLElement>("[data-key='app-menu']")!;
		tile.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await flush();
		await flush();
		return document.body.textContent ?? "";
	}

	it("offers All apps and Theme everywhere", async () => {
		const text = await opened({});
		expect(text).toContain("All apps");
		expect(text).toContain("Theme");
	});

	it("offers Customize sidebar inside an app", async () => {
		expect(await opened({ arrangeable: true })).toContain("Customize sidebar");
	});

	it("does not offer it on the index, which has no rail to arrange", async () => {
		expect(await opened({ arrangeable: false })).not.toContain("Customize sidebar");
	});

	it("offers Copy link only when the shell handed it one", async () => {
		expect(await opened({ shareLink: "https://x/apps/crm" })).toContain("Copy link");
		expect(await opened({})).not.toContain("Copy link");
	});
});

describe("an authored icon", () => {
	it("draws in the cell", async () => {
		await withSprite();

		const host = rail([{ ...doctype("CRM Deal"), icon: "users" }]);

		expect(cell(host, "CRM Deal")?.querySelector("use")?.getAttribute("href")).toBe(
			"#icon-users"
		);
	});

	it("gives way to the label's first letter when there is none", async () => {
		await withSprite();

		const host = rail([{ ...doctype("CRM Deal"), label: "Deals" }]);

		expect(cell(host, "CRM Deal")?.querySelector("use")).toBeNull();
		expect(target(host, "CRM Deal")?.textContent?.trim()).toBe("D");
	});
});
