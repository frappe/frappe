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
import SidebarOnly from "../SidebarOnly.vue";
import { useShellActs } from "../shellActs";

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
					h(SidebarOnly, { items: rail, contexts, sidebars, sections: {}, current, ...props });
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

const group = (host: HTMLElement) => host.querySelector("[data-key='deals']")!;
const header = (host: HTMLElement) => group(host).querySelector<HTMLButtonElement>("button")!;

describe("SidebarOnly", () => {
	it("draws the header, the navigation and the person's footer, 15rem wide, with no rail", () => {
		const host = mount();

		expect(host.querySelector("[data-key='app-menu']")).not.toBeNull();
		expect(host.querySelector("[data-key='palette-trigger']")?.textContent).toContain("Search");
		expect(host.querySelector("[data-key='user-menu']")).not.toBeNull();
		expect(host.querySelector("[data-slot='sidebar-rail']")).toBeNull();
		expect(host.querySelector<HTMLElement>("[data-slot='sidebar']")!.style.width).toBe("15rem");
	});

	it("makes a rail item that opens a sidebar a group, and any other rail item a row", () => {
		const host = mount();

		expect(group(host).getAttribute("data-sidebar")).toBe("site:aaaaaa");
		expect(header(host).getAttribute("aria-expanded")).toBe("false");
		const leads = host.querySelector("[data-key='leads']")!;
		expect(leads.querySelector("a")).not.toBeNull();
		expect(leads.querySelector("button")).toBeNull();
	});

	it("opens the current item's group and keeps the others shut", () => {
		const host = mount({ railKey: "deals", sidebar: "site:aaaaaa", rowKey: "all-deals" });

		expect(header(host).getAttribute("aria-expanded")).toBe("true");
		expect(group(host).querySelector("[data-key='all-deals']")).not.toBeNull();
	});

	it("lets a reader open and close a group", async () => {
		const host = mount();

		header(host).click();
		await nextTick();
		expect(group(host).querySelector("[data-key='all-deals']")).not.toBeNull();

		header(host).click();
		await nextTick();
		expect(group(host).querySelector("[data-key='all-deals']")).toBeNull();
	});

	it("keeps the rail item's group shut when its sidebar has no rows", () => {
		const host = mount({}, { sidebars: { "site:aaaaaa": [] } });

		expect(group(host).querySelector("button")).toBeNull();
		expect(group(host).querySelector("a")).not.toBeNull();
	});
});
