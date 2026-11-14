// The sidebar-only layout: rail items that open a sidebar are groups, the current group is open,
// an independent rail item is one row.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { generatedRoutes } from "@/router/generated";
import { registerShell } from "@/router/routeFor";
import { itemContext } from "@/navigation/context";
import type { CurrentNavigation } from "@/navigation/current";
import { installTranslate } from "@/i18n";
import PhoneNavigation from "../PhoneNavigation.vue";
import { useShellActs } from "../shellActs";
import { loadDocument } from "../tabKeepAlive";

vi.mock("../tabKeepAlive", () => ({ loadDocument: vi.fn() }));

registerStandardPages(standardPages);

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn() },
}));

const addresses = new Addresses({
	doctypes: { "CRM Deal": ["crm-deal", "fcrm"], "CRM Lead": ["crm-lead", "fcrm"] },
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

const rail: NavigationItem[] = [
	{ key: "deals", item_type: "DocType", link_to: "CRM Deal", opens_sidebar: "site:aaaaaa" },
	{ key: "leads", item_type: "DocType", link_to: "CRM Lead" },
	{ key: "wiki", item_type: "Link", label: "Wiki", url: "/wiki" },
];
const sidebars: Record<string, NavigationItem[]> = {
	"site:aaaaaa": [{ key: "all-deals", item_type: "DocType", link_to: "CRM Deal" }],
};

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

function mount(current: CurrentNavigation = {}, props: Record<string, unknown> = {}) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/", name: "home", component: { render: () => null } }, ...generatedRoutes(false)],
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
					rail: { customize: vi.fn(), sidebarCollapsed: () => null, toggleSidebar: () => {} },
				});
				const compose = (items: NavigationItem[]) =>
					itemContext(crm, addresses, router, items, sidebars);
				const contexts = {
					rail: compose(rail),
					sidebars: { "site:aaaaaa": compose(sidebars["site:aaaaaa"]) },
				};
				return () =>
					h(PhoneNavigation, { items: rail, contexts, sidebars, sections: {}, current, ...props });
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

const tabs = () =>
	[...document.querySelectorAll("[data-phone-nav] [data-slot='mobile-nav-item'], [data-phone-nav] [data-key='user-menu']")];

describe("PhoneNavigation", () => {
	it("draws a tab bar of Menu, Search and You while nothing fills the notifications slot", () => {
		mount();

		expect(tabs().map((tab) => tab.getAttribute("aria-label") ?? tab.textContent?.trim())).toEqual([
			"Menu",
			"Search",
			"You",
		]);
		expect(document.querySelector("[data-slot='sidebar-rail']")).toBeNull();
		expect(document.querySelector("[data-key='customize']")).toBeNull();
	});

	it("opens a sheet with the switcher, no utility rows, the rail tiles and the current sidebar's rows", async () => {
		mount({ railKey: "deals", sidebar: "site:aaaaaa", rowKey: "all-deals" });
		(tabs()[0] as HTMLElement).click();
		await nextTick();
		await nextTick();

		const sheet = document.querySelector("[data-phone-sheet]")!;
		expect(sheet.querySelector("[data-key='app-menu']")).not.toBeNull();
		expect(sheet.querySelector("[data-key='palette-trigger']")).toBeNull();
		expect([...sheet.querySelectorAll("[data-phone-tiles] > div")].map((tile) => tile.getAttribute("data-key"))).toEqual(["deals", "leads", "wiki"]);
		expect(sheet.querySelector("[data-phone-rows] [data-key='all-deals']")).not.toBeNull();
	});

	it("keeps the sheet open when a tile with a sidebar is tapped, and shows no rows for one without", async () => {
		mount();
		(tabs()[0] as HTMLElement).click();
		await nextTick();
		await nextTick();

		const tile = (key: string) =>
			document.querySelector<HTMLButtonElement>(`[data-phone-tiles] [data-key='${key}'] button`)!;
		tile("deals").click();
		await nextTick();
		expect(document.querySelector("[data-phone-rows] [data-key='all-deals']")).not.toBeNull();
		expect(document.querySelector("[data-phone-sheet]")).not.toBeNull();
	});

	it("loads a tile that leaves the shell through loadDocument, so a live window can keep the tab", async () => {
		mount();
		(tabs()[0] as HTMLElement).click();
		await nextTick();
		await nextTick();

		const tile = document.querySelector<HTMLElement>("[data-phone-tiles] [data-key='wiki']")!;
		(tile.querySelector("button, a") as HTMLElement).click();
		await nextTick();
		expect(loadDocument).toHaveBeenCalledWith("/wiki");
	});
});
