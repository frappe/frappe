// What the rail draws. Mounted with Vue's own `createApp`: this package has no `@vue/test-utils`.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App, type Ref } from "vue";
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

// `logout` posts through frappe-ui's `call`, and a toast needs a provider the rail lacks.
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	call: vi.fn().mockResolvedValue(null),
	toast: { success: vi.fn(), error: vi.fn() },
}));

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
	user: { name: "jane@example.com", full_name: "Jane Doe", email: "jane@example.com" },
} as unknown as Boot;

async function flush() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

// Every app mounted, unmounted before the body is wiped: a portal torn down after loses its nodes.
const mounted: App[] = [];

function unmountAll() {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
}

type Options = {
	sidebars?: Record<string, NavigationItem[]>;
	current?: string;
	customizable?: boolean;
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
				customizable: options.customizable,
				shareLink: options.shareLink,
			}),
	});
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	app.mount(host);
	mounted.push(app);

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
	return cell(host, key)?.querySelector("[data-slot='sidebar-rail-item']") ?? null;
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
	unmountAll();
	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	// `restoreAllMocks` leaves a `vi.fn()`'s call history alone.
	vi.clearAllMocks();
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
		// A full document load the router cannot resolve, and one `SidebarRailItem` cannot draw.
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
		unmountAll();
		const host = rail([], options);
		const tile = host.querySelector<HTMLElement>("[data-key='app-menu']")!;
		tile.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await flush();
		await flush();
		return document.body.textContent ?? "";
	}

	it("offers All apps everywhere, and Theme no longer: a theme is the person's", async () => {
		const text = await opened({});
		expect(text).toContain("All apps");
		expect(text).not.toContain("Theme");
	});

	it("offers Customize sidebar inside an app", async () => {
		expect(await opened({ customizable: true })).toContain("Customize sidebar");
	});

	it("does not offer it on the index, which has no rail to customize", async () => {
		expect(await opened({ customizable: false })).not.toContain("Customize sidebar");
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

describe("the person's cell", () => {
	function userCell(host: HTMLElement) {
		return host.querySelector<HTMLElement>("[data-key='user-menu']")!;
	}

	it("sits at the foot, named by the full name, with the initial as the fallback", () => {
		const host = rail([doctype("CRM Deal")]);
		const button = userCell(host);

		expect(button.getAttribute("aria-label")).toBe("Jane Doe");
		expect(button.textContent?.trim()).toBe("J");
		expect(button.querySelector("img")).toBeNull();
		// The same 28px as the rail's icon tiles.
		expect(button.firstElementChild?.className).toContain("w-7 h-7");
		// After the scrolling column, so the column's `flex-1` pins it to the foot.
		const scroll = host.querySelector("[data-key='CRM Deal']")!.closest("[data-slot='scroll-area']");
		expect(button.compareDocumentPosition(scroll!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
	});

	it("shows the person's image when boot carries one", () => {
		const boot = { ...crm, user: { ...crm.user, user_image: "/files/jane.png" } } as Boot;
		const image = userCell(rail([], { boot })).querySelector("img");
		expect(image?.getAttribute("src")).toBe("/files/jane.png");
	});
});

describe("the user menu", () => {
	/** The menu once opened from the keyboard; it renders in a portal on `body`. */
	async function opened(options: Options = {}) {
		unmountAll();
		const host = rail([], options);
		const button = host.querySelector<HTMLElement>("[data-key='user-menu']")!;
		button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await flush();
		await flush();
		return document.body.querySelector<HTMLElement>("[role='menu']")!;
	}

	/** The command rows: the profile header is a menuitem too, but a disabled one. */
	const COMMANDS = "[role='menuitem']:not([data-disabled])";

	function rows(menu: HTMLElement) {
		return Array.from(menu.querySelectorAll<HTMLElement>(COMMANDS)).map((row) =>
			row.textContent?.trim()
		);
	}

	function row(menu: HTMLElement, label: string) {
		return Array.from(menu.querySelectorAll<HTMLElement>(COMMANDS)).find(
			(node) => node.textContent?.trim() === label
		)!;
	}

	it("opens on a profile header: avatar, full name and email, not a command", async () => {
		const boot = { ...crm, user: { ...crm.user, user_image: "/files/jane.png" } } as Boot;
		const menu = await opened({ boot });
		const header = menu.querySelector<HTMLElement>("[data-key='profile']")!;

		expect(header.getAttribute("role")).toBe("menuitem");
		expect(header.hasAttribute("data-disabled")).toBe(true);
		expect(header.querySelector("img")?.getAttribute("src")).toBe("/files/jane.png");
		expect(header.textContent).toContain("Jane Doe");
		expect(header.textContent).toContain("jane@example.com");
		expect(rows(menu)).not.toContain("Jane Doe");
		// First, above the command rows.
		expect(menu.querySelector("[role='menuitem']")).toBe(header);
	});

	it("offers the four rows in order, with Log out in red", async () => {
		const menu = await opened();
		expect(rows(menu)).toEqual(["My settings", "Theme", "Desk v1", "Log out"]);
		expect(row(menu, "Log out").className).toContain("red");
	});

	it("separates the groups: the person's rows, Desk v1, Log out", async () => {
		const menu = await opened();
		const groups = Array.from(menu.querySelectorAll("[data-slot='group']")).map((group) =>
			Array.from(group.querySelectorAll(COMMANDS)).length
		);
		expect(groups).toEqual([0, 2, 1, 1]);
	});

	it("sends My settings to the person's v1 User form, and Desk v1 to v1's home", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});

		row(await opened(), "My settings").click();
		await flush();
		expect(assign).toHaveBeenLastCalledWith("/app/user/jane%40example.com");

		row(await opened(), "Desk v1").click();
		await flush();
		expect(assign).toHaveBeenLastCalledWith("/app");
	});

	it("asks before logging out, and Cancel keeps the session", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const { call } = await import("frappe-ui");

		row(await opened(), "Log out").click();
		await flush();

		const dialog = document.body.querySelector<HTMLElement>("[role='dialog']")!;
		expect(dialog.textContent).toContain("Log out?");
		expect(dialog.textContent).toContain("You will need to sign in again.");

		Array.from(dialog.querySelectorAll("button"))
			.find((button) => button.textContent?.trim() === "Cancel")!
			.click();
		await flush();

		expect(document.body.querySelector("[role='dialog']")).toBeNull();
		expect(call).not.toHaveBeenCalled();
		expect(assign).not.toHaveBeenCalled();
	});

	it("logs out on confirmation and goes to login with the way back, hash dropped", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const { call } = await import("frappe-ui");
		window.history.replaceState(null, "", "/crm-deal?sidebar=fcrm#customize/rail");

		row(await opened(), "Log out").click();
		await flush();
		Array.from(document.body.querySelector("[role='dialog']")!.querySelectorAll("button"))
			.find((button) => button.textContent?.trim() === "Log out")!
			.click();
		await flush();
		await flush();

		expect(call).toHaveBeenCalledWith("logout");
		expect(assign).toHaveBeenCalledWith("/login?redirect-to=%2Fcrm-deal%3Fsidebar%3Dfcrm");
		window.history.replaceState(null, "", "/");
	});

	it("keeps the dialog and toasts when the log out fails", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const { call, toast } = await import("frappe-ui");
		vi.mocked(call).mockRejectedValueOnce(new Error("offline"));

		row(await opened(), "Log out").click();
		await flush();
		Array.from(document.body.querySelector("[role='dialog']")!.querySelectorAll("button"))
			.find((button) => button.textContent?.trim() === "Log out")!
			.click();
		await flush();
		await flush();

		expect(document.body.querySelector("[role='dialog']")).not.toBeNull();
		expect(toast.error).toHaveBeenCalledWith("Could not log out");
		expect(assign).not.toHaveBeenCalled();
	});
});
