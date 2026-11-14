// The chrome the rail shares with the panel: the utility slots, the navigation header, the rail's
// `chrome` and `#foot`, the panel's `chrome` and the wide user menu. Mounted with Vue's own `createApp`.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { generatedRoutes } from "@/router/generated";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "@/navigation/context";
import RailColumn from "../RailColumn.vue";
import SidebarPanel from "../SidebarPanel.vue";
import { installTranslate } from "@/i18n";
import UserMenu from "../UserMenu.vue";
import UtilitySlots from "../UtilitySlots.vue";
import NavigationHeader from "../NavigationHeader.vue";
import { useShellActs } from "../shellActs";

registerStandardPages(standardPages);

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn() },
}));

const addresses = new Addresses({
	doctypes: { "CRM Deal": ["crm-deal", "fcrm"] },
	modules: { fcrm: "FCRM" },
});

const crm = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
	session: {
		user: { name: "jane@example.com", full_name: "Jane Doe", email: "jane@example.com" },
	},
} as unknown as Boot;

const items: NavigationItem[] = [{ key: "CRM Deal", item_type: "DocType", link_to: "CRM Deal" }];

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

// The shell composes the context and registers its acts; this stands in for it.
function mount(render: (context: ReturnType<typeof itemContext>) => ReturnType<typeof h>) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			...generatedRoutes(false),
		],
	});
	registerShell({ boot: crm, addresses, router });

	const app = createApp(
		defineComponent({
			setup() {
				useShellActs({
					boot: crm,
					router,
					openSettings: vi.fn(),
					openAbout: vi.fn(),
					confirmLogout: vi.fn(),
					rail: {
						customize: vi.fn(),
						sidebarCollapsed: () => null,
						toggleSidebar: () => {},
					},
				});
				const context = itemContext(crm, addresses, router, items, {});
				return () => render(context);
			},
		})
	);
	app.provide("boot", crm);
	app.provide("addresses", addresses);
	app.use(router);
	installTranslate(app);
	app.mount(host);
	mounted.push(app);
	return host;
}

function mountComponent(component: Component, props: Record<string, unknown> = {}, slots = {}) {
	return mount(() => h(component, props, slots));
}

const has = (host: HTMLElement, selector: string) => host.querySelector(selector) !== null;

describe("UtilitySlots", () => {
	it("draws search as a rail cell", () => {
		const host = mountComponent(UtilitySlots, { form: "cell" });
		const search = host.querySelector("[data-key='palette-trigger']")!;

		expect(search.getAttribute("aria-label")).toBe("Search");
		expect(search.className).toContain("size-7");
	});

	it("draws search as a row with its key", () => {
		const host = mountComponent(UtilitySlots, { form: "row" });
		const search = host.querySelector("[data-key='palette-trigger']")!;

		expect(search.textContent).toContain("Search");
		expect(search.querySelector("[data-slot='key']")).not.toBeNull();
	});

	it("draws nothing for notifications until the slot is filled", () => {
		const empty = mountComponent(UtilitySlots, { form: "row" });
		expect(empty.querySelectorAll("button")).toHaveLength(1);
		document.body.innerHTML = "";

		const filled = mountComponent(
			UtilitySlots,
			{ form: "row" },
			{ notifications: () => h("button", { "data-key": "notifications" }) }
		);
		const keys = Array.from(filled.querySelectorAll("button")).map((b) => b.dataset.key);
		expect(keys).toEqual(["palette-trigger", "notifications"]);
	});
});

describe("RailColumn chrome", () => {
	const rail = (props: Record<string, unknown> = {}, slots = {}) =>
		mount((context) => h(RailColumn, { items, context, ...props }, slots));

	it("draws the logo, the search cell and the avatar by default", () => {
		const host = rail();

		expect(has(host, "[data-key='app-menu']")).toBe(true);
		expect(has(host, "[data-key='palette-trigger']")).toBe(true);
		expect(has(host, "[data-key='user-menu']")).toBe(true);
	});

	it("draws only the items without it", () => {
		const host = rail({ chrome: false });

		expect(has(host, "[data-key='CRM Deal']")).toBe(true);
		expect(has(host, "[data-key='app-menu']")).toBe(false);
		expect(has(host, "[data-key='palette-trigger']")).toBe(false);
		expect(has(host, "[data-key='user-menu']")).toBe(false);
	});

	it("draws #foot at the foot, after the avatar, and nothing when it is empty", () => {
		const foot = { foot: () => h("button", { "data-key": "pin" }) };
		const host = rail({}, foot);
		const pin = host.querySelector("[data-key='pin']")!;
		const avatar = host.querySelector("[data-key='user-menu']")!;
		expect(avatar.compareDocumentPosition(pin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		document.body.innerHTML = "";

		expect(has(rail({ chrome: false }, foot), "[data-key='pin']")).toBe(true);
		document.body.innerHTML = "";
		expect(has(rail({ chrome: false }), "[data-key='pin']")).toBe(false);
	});
});

describe("NavigationHeader", () => {
	it("draws the app's title as one button with the search row under it", () => {
		const host = mountComponent(NavigationHeader);
		const tile = host.querySelector("[data-key='app-menu']")!;
		const search = host.querySelector("[data-key='palette-trigger']")!;

		expect(tile.textContent).toContain("CRM");
		expect(tile.getAttribute("aria-label")).toBe("CRM menu");
		expect(tile.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
	});

	it("opens the app menu", async () => {
		const host = mountComponent(NavigationHeader);
		host.querySelector<HTMLElement>("[data-key='app-menu']")!.dispatchEvent(
			new MouseEvent("pointerdown", { bubbles: true, button: 0 })
		);
		await nextTick();
		await nextTick();

		expect(document.body.textContent).toContain("All apps");
	});
});

describe("SidebarPanel chrome", () => {
	const panel = (chrome: boolean) =>
		mount((context) =>
			h(SidebarPanel, {
				address: "crm",
				items,
				context,
				title: "Deals",
				collapsed: false,
				chrome,
			})
		);

	it("carries the header, the avatar row and no seam", () => {
		const host = panel(true);

		expect(has(host, "[data-key='app-menu']")).toBe(true);
		expect(host.querySelector("[data-key='user-menu']")?.textContent).toContain("Jane Doe");
		expect(host.querySelector("[data-slot='sidebar']")?.className).toContain("border-0");
	});

	it("is the plain panel without it", () => {
		const host = panel(false);

		expect(has(host, "[data-key='app-menu']")).toBe(false);
		expect(has(host, "[data-key='user-menu']")).toBe(false);
		expect(host.querySelector("[data-slot='sidebar']")?.className).toContain("border-l");
	});
});

describe("SidebarPanel links", () => {
	it("opens another origin in a new tab with an arrow, and a path on this site in place", () => {
		const host = mount((context) =>
			h(SidebarPanel, {
				address: "crm",
				items: [
					{ key: "docs", item_type: "Link", url: "https://docs.frappe.io" },
					{ key: "here", item_type: "Link", url: "/app/todo" },
				],
				context,
				title: "Deals",
				collapsed: false,
			})
		);
		const anchor = (key: string) => host.querySelector(`[data-key='${key}'] a`)!;

		expect(anchor("docs").getAttribute("target")).toBe("_blank");
		expect(anchor("docs").getAttribute("rel")).toBe("noopener");
		expect(anchor("docs").querySelector(".lucide-arrow-up-right")).not.toBeNull();
		expect(anchor("docs").textContent).toContain("Opens in a new tab");
		expect(anchor("here").getAttribute("target")).toBeNull();
		expect(anchor("here").querySelector(".lucide-arrow-up-right")).toBeNull();
	});
});

describe("UserMenu wide", () => {
	it("draws the avatar with the full name, and the cell without it", () => {
		const wide = mountComponent(UserMenu, { wide: true }).querySelector("[data-key='user-menu']")!;
		expect(wide.textContent).toContain("Jane Doe");
		document.body.innerHTML = "";

		const cell = mountComponent(UserMenu).querySelector("[data-key='user-menu']")!;
		expect(cell.textContent).not.toContain("Jane Doe");
		expect(cell.getAttribute("aria-label")).toBe("Jane Doe");
	});
});
