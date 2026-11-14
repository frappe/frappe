// The shell drawn on the right: DesktopShell's side, the borders, the seam, the menus' side and the inset the floats read.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("frappe-ui", async (importOriginal) => {
	const actual = await importOriginal<typeof import("frappe-ui")>();
	// Menus and tooltips open on hover or click; their side is all this test reads.
	const sideOf = (name: string) =>
		defineComponent({
			props: { side: String, options: Array, align: String, text: String },
			setup: (props, { slots }) => () => h("div", { [`data-${name}`]: props.side }, slots.default?.()),
		});
	return { ...actual, Dropdown: sideOf("dropdown"), Tooltip: sideOf("tooltip") };
});

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { navInsetRight } from "../navigationInset";
import { navigationSide } from "../navigationSide";

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { accounts: "Accounts" },
});
const stub = { render: () => null };

const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const docs: NavigationItem = {
	key: "docs",
	item_type: "Link",
	label: "Docs",
	url: "https://docs.frappe.io",
};
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

const WINDOW = 1024;
const RAIL = 50;
const PANEL = 224;
const mounted: App[] = [];

async function flush() {
	await Promise.resolve();
	await nextTick();
	await nextTick();
}

function session(own: string, site?: string) {
	return {
		user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com", navigation_side: own },
		defaults: site ? { navigation_side: site } : {},
	};
}

async function shell(own: string, site?: string, boot: Partial<Boot> = {}): Promise<HTMLElement> {
	const full = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: { rail: [accounts, docs], sidebars },
		session: session(own, site),
		...boot,
	} as unknown as Boot;
	const router = boot.app === null ? createShellRouter(full, addresses) : createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:doctype", name: "list", component: stub }],
	});
	registerShell({ boot: full, addresses, router });
	const host = document.body.appendChild(document.createElement("div"));
	const app = createApp(AppShell);
	app.provide("boot", full);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push(boot.app === null ? "/" : "/sales-invoice");
	await router.isReady();
	app.mount(host);
	mounted.push(app);
	await flush();
	return host;
}

const root = (host: HTMLElement) => host.querySelector<HTMLElement>("[data-slot='desktop-shell']")!;
const panel = (host: HTMLElement) => host.querySelector<HTMLElement>("[data-slot='sidebar']")!;
/** The seam, drawn right after the panel. */
const seam = (host: HTMLElement) => panel(host).nextElementSibling as HTMLElement;
/** The `side` each menu or tooltip got: the app menu then the avatar menu; the search cell then the off-prefix link. */
const sides = (host: HTMLElement, kind: "dropdown" | "tooltip") =>
	[...host.querySelectorAll(`[data-${kind}]`)].map((element) => element.getAttribute(`data-${kind}`));
const chevron = (host: HTMLElement) => host.querySelector(".lucide-chevron-left")!;
const pointer = (target: EventTarget, type: string, clientX: number) =>
	target.dispatchEvent(new MouseEvent(type, { clientX, bubbles: true }));

beforeAll(async () => {
	registerStandardPages(standardPages);
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	localStorage.clear();
	resetNavigationReports();
	resetSprite();
	navigationSide.value = "start";
	Object.defineProperty(document.documentElement, "clientWidth", { value: WINDOW, configurable: true });
	// The content fills what the rail and an open panel leave.
	vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
		const open = document.querySelector("[data-slot='sidebar']")?.getAttribute("data-state") === "expanded";
		const width = this.dataset.slot === "desktop-shell-content" ? WINDOW - RAIL - (open ? PANEL : 0) : 0;
		return { width, height: 0, left: 0, top: 0, right: width, bottom: 0, x: 0, y: 0 } as DOMRect;
	});
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	vi.restoreAllMocks();
});

describe("on the left", () => {
	it("draws as before: DesktopShell on the left, the panel's border on its left, the seam on its right", async () => {
		const host = await shell("");
		expect(root(host).className).not.toContain("flex-row-reverse");
		expect(root(host).className).not.toContain("nav-right");
		expect(panel(host).className).toContain("border-l");
		expect(seam(host).className).toContain("left-full");
		expect(seam(host).className).toContain("cursor-w-resize");
		expect(chevron(host).className).not.toContain("rotate-180");
		expect(navInsetRight.value).toBe(0);
		expect(document.documentElement.style.getPropertyValue("--shell-nav-inset-right")).toBe("0px");
	});

	it("opens the rail's menus, avatar menu and tooltips to the right", async () => {
		const host = await shell("start");
		expect(sides(host, "dropdown")).toEqual(["right", "right"]);
		expect(sides(host, "tooltip")).toEqual(["right", "right"]);
	});
});

describe("on the right", () => {
	it("hands DesktopShell nav-side right, and draws the content's border on its right", async () => {
		const host = await shell("end");
		expect(root(host).className).toContain("flex-row-reverse");
		expect(root(host).className).toContain("nav-right");
	});

	it("follows the site's value while the person's is blank", async () => {
		expect(root(await shell("", "end")).className).toContain("nav-right");
		expect(root(await shell("start", "end")).className).not.toContain("nav-right");
	});

	it("draws the panel's border on its right", async () => {
		const panelClass = panel(await shell("end")).className;
		expect(panelClass).toContain("border-r");
		expect(panelClass).not.toContain("border-l");
	});

	it("flips the seam: its place, the cursors, the chevron", async () => {
		const host = await shell("end");
		expect(seam(host).className).toContain("right-full");
		expect(seam(host).className).toContain("cursor-e-resize");
		expect(chevron(host).className).toContain("rotate-180");

		seam(host).click();
		await flush();
		expect(seam(host).className).toContain("cursor-w-resize");
		expect(chevron(host).className).not.toContain("rotate-180");
	});

	it("collapses on a drag toward the rail, which is to the right, and ignores one away from it", async () => {
		const host = await shell("end");

		pointer(seam(host), "pointerdown", 300);
		pointer(window, "pointermove", 250);
		pointer(window, "pointerup", 250);
		await flush();
		expect(panel(host).getAttribute("data-state")).toBe("expanded");

		pointer(seam(host), "pointerdown", 300);
		pointer(window, "pointermove", 350);
		await flush();
		expect(panel(host).getAttribute("data-state")).toBe("collapsed");
	});

	it("opens the rail's menus, avatar menu and tooltips to the left", async () => {
		const host = await shell("end");
		expect(sides(host, "dropdown")).toEqual(["left", "left"]);
		expect(sides(host, "tooltip")).toEqual(["left", "left"]);
	});

	it("sets the inset to the rail plus the open panel, and to the rail alone once it collapses", async () => {
		const host = await shell("end");
		const inset = () => document.documentElement.style.getPropertyValue("--shell-nav-inset-right");
		expect(inset()).toBe(`${RAIL + PANEL}px`);
		expect(navInsetRight.value).toBe(RAIL + PANEL);

		seam(host).click();
		await flush();
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(inset()).toBe(`${RAIL}px`);
	});

	it("clears the inset when the shell goes", async () => {
		await shell("end");
		mounted.splice(0).forEach((app) => app.unmount());
		expect(navInsetRight.value).toBe(0);
		expect(document.documentElement.style.getPropertyValue("--shell-nav-inset-right")).toBe("");
	});
});

describe("the apps index", () => {
	const index = { app: null, shell_base: "/apps", prefixes: {}, apps: [], navigation: undefined };
	const foot = (host: HTMLElement) => host.querySelector<HTMLElement>("[data-index-foot]")!;

	it("keeps its avatar at the bottom left", async () => {
		const host = await shell("start", undefined, index as unknown as Partial<Boot>);
		expect(foot(host).className).toContain("left-[11px]");
	});

	it("moves its avatar to the bottom right, and opens its menu to the left", async () => {
		const host = await shell("end", undefined, index as unknown as Partial<Boot>);
		expect(foot(host).className).toContain("right-[11px]");
		expect(foot(host).className).not.toContain("left-[11px]");
		expect(foot(host).querySelector("[data-dropdown]")!.getAttribute("data-dropdown")).toBe("left");
	});
});
