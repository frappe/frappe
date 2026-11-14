// The floating rail in the shell: where the rail is drawn, what carries the chrome, and the pin and unpin saves.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const { runMethod, toastError } = vi.hoisted(() => ({ runMethod: vi.fn(), toastError: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...((await importOriginal()) as object),
	runMethod,
}));
vi.mock("frappe-ui", async (importOriginal) => {
	const actual = await importOriginal<typeof import("frappe-ui")>();
	return { ...actual, toast: { error: toastError, success: vi.fn() } };
});

import { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem, NavigationLayout } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { installTranslate } from "@/i18n";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { canPin, navigationLayout, pinned } from "../navigationLayout";
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
const docs: NavigationItem = { key: "docs", item_type: "Link", label: "Docs", url: "https://docs.frappe.io" };
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

const mounted: App[] = [];

async function flush() {
	for (let tick = 0; tick < 4; tick++) await Promise.resolve();
	await nextTick();
	await nextTick();
}

/** A window `width` wide on a device that can (or cannot) hover. */
function device(width: number, hover = true) {
	Object.defineProperty(window, "innerWidth", { value: width, configurable: true });
	window.matchMedia = ((query: string) => {
		const min = /min-width:\s*(\d+)px/.exec(query);
		const matches = min ? width >= Number(min[1]) : query.includes("any-hover") ? hover : false;
		return {
			matches,
			media: query,
			addEventListener: () => {},
			removeEventListener: () => {},
			addListener: () => {},
			removeListener: () => {},
		} as unknown as MediaQueryList;
	}) as typeof window.matchMedia;
}

// A floating rail may be pinned unless `canPin` is off: the layout below it is another one.
function navigation(
	layout: NavigationLayout,
	pinnedLayout = false,
	rail = [accounts, docs],
	canPin = layout === "floating_rail"
): Navigation {
	return {
		rail,
		sidebars,
		navigation_layout: layout,
		...(pinnedLayout ? { pinned: true as const } : {}),
		...(canPin ? { can_pin: true as const } : {}),
	};
}

async function shell(nav: Navigation, side = "", path = "/sales-invoice"): Promise<HTMLElement> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: nav,
		session: {
			user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com", navigation_side: side },
			defaults: {},
		},
	} as unknown as Boot;
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:doctype", name: "list", component: stub }],
	});
	registerShell({ boot, addresses, router });
	const host = document.body.appendChild(document.createElement("div"));
	const app = createApp(defineComponent({ render: () => h(AppShell) }));
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	installTranslate(app);
	await router.push(path);
	await router.isReady();
	app.mount(host);
	mounted.push(app);
	await flush();
	return host;
}

const box = (host: HTMLElement) => host.querySelector<HTMLElement>("[data-floating-rail]");
const rails = (host: HTMLElement) => host.querySelectorAll("[data-slot='sidebar-rail']");
const panel = (host: HTMLElement) => host.querySelector<HTMLElement>("[data-slot='sidebar']");
const key = (host: HTMLElement | Element, name: string) => host.querySelector<HTMLElement>(`[data-key='${name}']`);

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
	navigationLayout.value = "rail_and_sidebar";
	pinned.value = false;
	canPin.value = false;
	runMethod.mockReset();
	toastError.mockReset();
	device(1280);
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
});

describe("a floating rail", () => {
	it("draws the rail only inside its box, and no seam beside the sidebar", async () => {
		const host = await shell(navigation("floating_rail"));

		expect(rails(host)).toHaveLength(1);
		expect(box(host)!.contains(rails(host)[0])).toBe(true);
		expect(box(host)!.getAttribute("data-open")).toBe("false");
		expect(panel(host)).not.toBeNull();
		expect(host.querySelector("[class*='cursor-w-resize'], [class*='cursor-e-resize']")).toBeNull();
	});

	it("takes the box to the navigation's side", async () => {
		expect(box(await shell(navigation("floating_rail"), "start"))!.className).toContain("left-2");
		mounted.splice(0).forEach((app) => app.unmount());
		expect(box(await shell(navigation("floating_rail"), "end"))!.className).toContain("right-2");
	});

	it("leaves the sidebar the chrome, and the rail the pin button", async () => {
		const host = await shell(navigation("floating_rail"));

		expect(key(panel(host)!, "app-menu")).not.toBeNull();
		expect(key(panel(host)!, "user-menu")).not.toBeNull();
		expect(key(box(host)!, "app-menu")).toBeNull();
		expect(key(box(host)!, "user-menu")).toBeNull();
		expect(key(box(host)!, "pin-navigation")).not.toBeNull();
		expect(key(host, "unpin-navigation")).toBeNull();
	});

	it("carries the chrome itself on a page with no sidebar", async () => {
		const host = await shell(navigation("floating_rail", false, [docs]));

		expect(panel(host)).toBeNull();
		expect(key(box(host)!, "app-menu")).not.toBeNull();
		expect(key(box(host)!, "user-menu")).not.toBeNull();
	});

	it("does not customize or collapse the sidebar from there", async () => {
		const host = await shell(navigation("floating_rail"));

		expect(panel(host)!.querySelector("[aria-label='Customize this sidebar']")).toBeNull();
		expect(panel(host)!.getAttribute("data-state")).toBe("expanded");
	});

	it("draws the rail beside the sidebar when the device cannot hover", async () => {
		device(1280, false);
		const host = await shell(navigation("floating_rail"));

		expect(box(host)).toBeNull();
		expect(rails(host)).toHaveLength(1);
	});
});

describe("pin", () => {
	it("saves the person's layout as rail + sidebar and docks the rail, with an unpin button", async () => {
		runMethod.mockResolvedValue({ data: navigation("rail_and_sidebar", true) });
		const host = await shell(navigation("floating_rail"));

		key(box(host)!, "pin-navigation")!.click();
		await flush();

		expect(runMethod).toHaveBeenCalledTimes(1);
		expect(runMethod).toHaveBeenCalledWith("frappe.shell.arrangement.save_navigation_layout", {
			app: "crm",
			navigation_layout: "rail_and_sidebar",
			scope: "user",
		});
		expect(box(host)).toBeNull();
		expect(rails(host)).toHaveLength(1);
		expect(key(rails(host)[0], "unpin-navigation")).not.toBeNull();
		expect(key(host, "pin-navigation")).toBeNull();
		// Docked, the sidebar is customizable again.
		expect(panel(host)!.querySelector("[aria-label='Customize this sidebar']")).not.toBeNull();
	});

	it("ignores a second press while the save runs, and moves focus to the unpin button", async () => {
		let finish!: (value: unknown) => void;
		runMethod.mockReturnValue(new Promise((resolve) => (finish = resolve)));
		const host = await shell(navigation("floating_rail"));
		const button = key(box(host)!, "pin-navigation")!;

		button.click();
		button.click();
		finish({ data: navigation("rail_and_sidebar", true) });
		await flush();

		expect(runMethod).toHaveBeenCalledTimes(1);
		expect(document.activeElement).toBe(key(rails(host)[0], "unpin-navigation"));
	});

	it("says so and keeps the rail floating when the save fails", async () => {
		runMethod.mockRejectedValue(new Error("Not permitted"));
		const host = await shell(navigation("floating_rail"));

		key(box(host)!, "pin-navigation")!.click();
		await flush();

		expect(toastError).toHaveBeenCalledWith("Not permitted");
		expect(box(host)).not.toBeNull();
	});
});

describe("a floating rail over another layout", () => {
	it("offers no pin, since the person could not unpin it again", async () => {
		const host = await shell(navigation("floating_rail", false, [accounts, docs], false));

		expect(box(host)).not.toBeNull();
		expect(key(box(host)!, "pin-navigation")).toBeNull();
	});
});

describe("unpin", () => {
	it("is on a pinned rail only, and lets the rail float again", async () => {
		runMethod.mockResolvedValue({ data: navigation("floating_rail") });
		const host = await shell(navigation("rail_and_sidebar", true));
		expect(box(host)).toBeNull();

		key(rails(host)[0], "unpin-navigation")!.click();
		await flush();

		expect(runMethod).toHaveBeenCalledWith("frappe.shell.arrangement.save_navigation_layout", {
			app: "crm",
			navigation_layout: "floating_rail",
			scope: "user",
		});
		expect(box(host)).not.toBeNull();
		expect(key(host, "unpin-navigation")).toBeNull();
	});

	it("is not drawn on a rail that nothing pinned", async () => {
		const host = await shell(navigation("rail_and_sidebar"));

		expect(rails(host)).toHaveLength(1);
		expect(key(host, "unpin-navigation")).toBeNull();
		expect(key(host, "pin-navigation")).toBeNull();
	});

	it("is not drawn while the pinned layout draws as something else", async () => {
		const host = await shell(navigation("sidebar_only", true));

		expect(key(host, "unpin-navigation")).toBeNull();
	});
});
