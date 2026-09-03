// What the rail draws. Mounted with Vue's own `createApp`: this package has no `@vue/test-utils`.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type Ref } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { generatedRoutes } from "@/router/generated";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "@/navigation/context";
import { resetNavigationReports } from "@/navigation/registry";
import { loadSprite, resetSprite } from "@/icons/sprite";
import AppRail from "../AppRail.vue";

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"CRM Lead": ["crm-lead", "fcrm"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { fcrm: "FCRM", accounts: "Accounts" },
});

const boot = {
	app: "crm",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
} as unknown as Boot;

async function flush() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

/** The mounted rail plus the list it renders, so a test can replace it as a save does. */
function mount(
	initial: NavigationItem[],
	sidebars: Record<string, NavigationItem[]> = {}
): { host: HTMLElement; items: Ref<NavigationItem[]> } {
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
			h(AppRail, {
				items: items.value,
				context: itemContext(boot, addresses, router, items.value, sidebars),
			}),
	});
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	app.mount(host);

	return { host, items };
}

function rail(
	items: NavigationItem[],
	sidebars: Record<string, NavigationItem[]> = {}
) {
	return mount(items, sidebars).host;
}

function row(host: HTMLElement, key: string) {
	return host.querySelector(`[data-key="${CSS.escape(key)}"]`);
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

describe("the kinds the rail used to drop", () => {
	it("draws all of them, not only DocType", () => {
		// It once drew only `DocType` rows and dropped the other seven.
		const host = rail([
			doctype("CRM Deal"),
			{ key: "docs", item_type: "Link", url: "https://docs.frappe.io" },
			{ key: "reports", item_type: "Section" },
			{ key: "invoice", item_type: "Record", link_doctype: "CRM Deal", link_to: "D-1" },
		]);

		expect(row(host, "CRM Deal")).not.toBeNull();
		expect(row(host, "docs")).not.toBeNull();
		expect(row(host, "invoice")).not.toBeNull();
	});

	it("makes a Link a plain anchor, not a router link", () => {
		// Following it leaves this prefix: a full document load the router cannot resolve.
		const host = rail([{ key: "docs", item_type: "Link", url: "https://docs.frappe.io" }]);
		const anchor = row(host, "docs") as HTMLAnchorElement;
		expect(anchor.tagName).toBe("A");
		expect(anchor.getAttribute("href")).toBe("https://docs.frappe.io");
	});

	it("makes a DocType an in-prefix link", () => {
		const host = rail([doctype("CRM Deal")]);
		expect((row(host, "CRM Deal") as HTMLAnchorElement).getAttribute("href")).toBe(
			"/crm-deal"
		);
	});
});

describe("sections and nesting", () => {
	it("draws a section as a heading and files its children under it", () => {
		const host = rail([
			{ key: "sales", item_type: "Section", label: "Sales" },
			doctype("CRM Deal", "sales"),
		]);

		const heading = row(host, "sales")!;
		expect(heading.textContent).toContain("Sales");
		// The child is inside the section's own list item, not an indent class on a flat list.
		expect(heading.closest("li")!.contains(row(host, "CRM Deal"))).toBe(true);
	});

	it("nests to a third level", () => {
		const host = rail([
			{ key: "a", item_type: "Section" },
			{ key: "b", item_type: "Section", parent_key: "a" },
			doctype("CRM Deal", "b"),
		]);
		expect(row(host, "b")!.closest("li")!.contains(row(host, "CRM Deal"))).toBe(true);
		expect(row(host, "a")!.closest("li")!.contains(row(host, "b"))).toBe(true);
	});

	it("gives a plain section no control, because most are not closable", () => {
		const host = rail([{ key: "sales", item_type: "Section" }, doctype("CRM Deal", "sales")]);
		expect(row(host, "sales")!.tagName).toBe("P");
	});

	it("makes a collapsible section a button that closes it", async () => {
		const host = rail([
			{ key: "sales", item_type: "Section", collapsible: 1 },
			doctype("CRM Deal", "sales"),
		]);
		const heading = row(host, "sales") as HTMLButtonElement;

		expect(heading.tagName).toBe("BUTTON");
		expect(heading.getAttribute("aria-expanded")).toBe("true");

		heading.click();
		await flush();

		expect(row(host, "CRM Deal")).toBeNull();
		expect(row(host, "sales")!.getAttribute("aria-expanded")).toBe("false");
	});

	it("starts a keep_closed section closed", () => {
		const host = rail([
			{ key: "sales", item_type: "Section", collapsible: 1, keep_closed: 1 },
			doctype("CRM Deal", "sales"),
		]);
		expect(row(host, "CRM Deal")).toBeNull();
	});

	it("keeps a heading whose own renderer is missing, and its children", () => {
		// The same choice `_promote_orphans` makes on the server: an item that cannot be
		// placed never silently takes what is under it.
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([
			{ key: "mystery", item_type: "Chart", label: "Charts" },
			doctype("CRM Deal", "mystery"),
		]);
		expect(row(host, "mystery")!.textContent).toContain("Charts");
		expect(row(host, "CRM Deal")).not.toBeNull();
	});
});

describe("a linked item", () => {
	it("carries the sidebar it opens, so the panel can mount off it", () => {
		// A `Sidebar` item is what makes a rail item linked; the rail draws it so whether or not
		// a panel exists.
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
				module_def_accounts: [
					{ key: "Sales Invoice", item_type: "DocType", link_to: "Sales Invoice" },
				],
			}
		);

		const link = row(host, "accounts") as HTMLAnchorElement;
		expect(link.getAttribute("data-sidebar")).toBe("module_def_accounts");
		// Real navigation, not shell state: the panel is named in the href, so middle-click works.
		expect(link.getAttribute("href")).toBe("/sales-invoice?sidebar=module_def_accounts");
	});

	it("is not drawn when its sidebar is absent", () => {
		const host = rail([
			{ key: "accounts", item_type: "Sidebar", link_to: "module_def_accounts" },
		]);
		expect(row(host, "accounts")).toBeNull();
	});
});

describe("Module Contents", () => {
	const overflow: NavigationItem = {
		key: "more",
		item_type: "Module Contents",
		link_doctype: "Module Def",
		link_to: "Accounts",
		label: "More",
	};

	it("is a button, and reveals the rest of the module on click", async () => {
		const fetched = vi.fn().mockResolvedValue([
			{ doctype: "Sales Invoice", slug: "sales-invoice", module: "accounts" },
		]);
		const host = rail([overflow]);
		// The context is built in the component, so the fetch is stubbed at its source.
		const contents = await import("@/contents");
		vi.spyOn(contents, "fetchContents").mockImplementation(fetched);

		const button = row(host, "more") as HTMLButtonElement;
		expect(button.tagName).toBe("BUTTON");
		expect(button.getAttribute("aria-expanded")).toBe("false");

		button.click();
		await flush();

		expect(fetched).toHaveBeenCalledWith("crm", "accounts");
		expect(row(host, "more:Sales Invoice")).not.toBeNull();
		// At the row's OWN level: "N more" is an overflow of the list it is in, so indenting
		// what it reveals would say the module contains the overflow row.
		expect(row(host, "more:Sales Invoice")!.closest("ul")).toBe(
			row(host, "more")!.closest("ul")
		);
	});

	it("stays collapsed and says so when the fetch fails", async () => {
		const logged = vi.spyOn(console, "error").mockImplementation(() => {});
		const contents = await import("@/contents");
		vi.spyOn(contents, "fetchContents").mockRejectedValue(new Error("offline"));

		const host = rail([overflow]);
		(row(host, "more") as HTMLButtonElement).click();
		await flush();

		// Expanding is the one thing on the rail that costs a request, so the one that can fail
		// from a dropped connection.
		expect(row(host, "more")!.getAttribute("aria-expanded")).toBe("false");
		expect(logged).toHaveBeenCalled();
	});
});

describe("a row that cannot be drawn", () => {
	it("is skipped, and the rest of the rail still renders", () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([{ key: "x", item_type: "Chart" }, doctype("CRM Deal")]);
		expect(row(host, "x")).toBeNull();
		expect(row(host, "CRM Deal")).not.toBeNull();
	});

	it("does not blank the rail when a renderer throws", () => {
		vi.spyOn(console, "error").mockImplementation(() => {});
		const host = rail([doctype("Nonexistent Doctype"), doctype("CRM Deal")]);
		expect(row(host, "Nonexistent Doctype")).toBeNull();
		expect(row(host, "CRM Deal")).not.toBeNull();
	});
});

describe("an expanded overflow row when the list changes under it", () => {
	it("collapses rather than keeping rows it worked out about the old list", async () => {
		// A save swaps in a new list while the component survives (`v-for` keys on the key), so
		// what the expansion showed was measured against a list that no longer exists.
		const contents = await import("@/contents");
		vi.spyOn(contents, "fetchContents").mockResolvedValue([
			{ doctype: "Sales Invoice", slug: "sales-invoice", module: "accounts" },
		]);

		const overflow: NavigationItem = {
			key: "more",
			item_type: "Module Contents",
			link_doctype: "Module Def",
			link_to: "Accounts",
			label: "More",
		};
		const { host, items } = mount([overflow]);

		(row(host, "more") as HTMLButtonElement).click();
		await flush();
		expect(row(host, "more:Sales Invoice")).not.toBeNull();

		items.value = [overflow, doctype("Sales Invoice")];
		await flush();

		expect(row(host, "more:Sales Invoice")).toBeNull();
		expect(row(host, "more")!.getAttribute("aria-expanded")).toBe("false");
		expect(row(host, "Sales Invoice")).not.toBeNull();
	});
});

describe("a section's disclosure when the list changes under it", () => {
	const section = (extra: Partial<NavigationItem> = {}): NavigationItem => ({
		key: "sales",
		item_type: "Section",
		label: "Sales",
		collapsible: 1,
		...extra,
	});

	it("follows a reset that ships a different keep_closed", () => {
		// A reset returns the app's own layer while the component survives, so the same key
		// comes back with a different shipped value.
		const { host, items } = mount([section({ keep_closed: 1 }), doctype("CRM Deal", "sales")]);
		expect(row(host, "CRM Deal")).toBeNull();

		items.value = [section(), doctype("CRM Deal", "sales")];
		return nextTick().then(() => {
			expect(row(host, "CRM Deal")).not.toBeNull();
		});
	});

	it("does not re-open what the reader just closed", async () => {
		// The watch is on the shipped value, not the row: a toggle changes `open` and never
		// `keep_closed`, so a save that leaves the section alone leaves it closed.
		const { host, items } = mount([section(), doctype("CRM Deal", "sales")]);

		(row(host, "sales") as HTMLButtonElement).click();
		await flush();
		expect(row(host, "CRM Deal")).toBeNull();

		items.value = [section(), doctype("CRM Deal", "sales"), doctype("CRM Lead")];
		await flush();

		expect(row(host, "CRM Deal")).toBeNull();
		expect(row(host, "CRM Lead")).not.toBeNull();
	});
});


describe("an authored icon", () => {
	// Every rail row CRM and ERPNext ship carries one; every sidebar row but four does not.
	it("draws beside the label", async () => {
		await withSprite();

		const host = rail([{ ...doctype("CRM Deal"), icon: "users" }]);

		expect(row(host, "CRM Deal")?.querySelector("use")?.getAttribute("href")).toBe(
			"#icon-users"
		);
	});

	it("leaves the label readable", async () => {
		await withSprite();

		const host = rail([{ ...doctype("CRM Deal"), icon: "users", label: "Deals" }]);

		expect(row(host, "CRM Deal")?.textContent?.trim()).toBe("Deals");
	});

	it("is not drawn on a Section heading", async () => {
		// A section that carries one has it ignored, never refused.
		await withSprite();

		const host = rail([
			{ key: "sales", item_type: "Section", label: "Sales", icon: "users" },
			doctype("CRM Deal", "sales"),
		]);

		expect(row(host, "sales")?.querySelector("use")).toBeNull();
		expect(row(host, "sales")?.textContent?.trim()).toBe("Sales");
	});

	it("holds the slot open on the rows that have none", async () => {
		// Decided for the whole container, so one unadorned row still reads as part of it.
		await withSprite();

		const host = rail([{ ...doctype("CRM Deal"), icon: "users" }, doctype("CRM Lead")]);

		expect(row(host, "CRM Lead")?.querySelector("span[aria-hidden]")).not.toBeNull();
	});

	it("holds no slot open in a container where nothing has one", async () => {
		await withSprite();

		const host = rail([doctype("CRM Deal"), doctype("CRM Lead")]);

		expect(row(host, "CRM Deal")?.querySelector("span[aria-hidden]")).toBeNull();
	});

	it("holds none open for an icon only a heading carries", async () => {
		// A heading draws no icon, so one on a section would indent every row under it
		// for a slot nothing fills.
		await withSprite();

		const host = rail([
			{ key: "sales", item_type: "Section", label: "Sales", icon: "users" },
			doctype("CRM Deal", "sales"),
		]);

		expect(row(host, "CRM Deal")?.querySelector("span[aria-hidden]")).toBeNull();
	});
});
