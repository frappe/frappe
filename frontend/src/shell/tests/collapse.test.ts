// The panel's collapse: the edge button, the drag on the seam, and the store that keeps it.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";

const STORE = "frappe:desk:collapsed-sidebar";
const READER = "reader@example.com";

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
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

async function flush() {
	await Promise.resolve();
	await nextTick();
}

async function shell(user = READER): Promise<HTMLElement> {
	const boot = {
		app: "crm",
		shell_base: "/apps/crm",
		prefixes: { crm: { app: "crm", modular: false } },
		navigation: { rail: [accounts], sidebars },
		session: {
			user: { name: user, full_name: "Reader", email: user },
		},
	} as unknown as Boot;

	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
		],
	});
	registerShell({ boot, addresses, router });

	const host = document.createElement("div");
	document.body.appendChild(host);

	const app = createApp(AppShell);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);

	await router.push("/sales-invoice");
	await router.isReady();
	app.mount(host);
	await flush();

	return host;
}

function panel(host: HTMLElement) {
	return host.querySelector("[data-slot='sidebar']")!;
}

function state(host: HTMLElement) {
	return panel(host).getAttribute("data-state");
}

/** The seam: the strip on the panel's outer edge, drawn right after the panel. */
function seam(host: HTMLElement) {
	return panel(host).nextElementSibling as HTMLElement;
}

function pointer(target: EventTarget, type: string, clientX: number) {
	target.dispatchEvent(new MouseEvent(type, { clientX, bubbles: true }));
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	document.body.innerHTML = "";
	localStorage.clear();
	window.history.replaceState(null, "", "/");
	resetNavigationReports();
	resetSprite();
	vi.unstubAllGlobals();
});

describe("the edge button", () => {
	it("collapses the panel, takes it out of the tab order, and the store keeps it", async () => {
		const host = await shell();
		expect(state(host)).toBe("expanded");

		host.querySelector<HTMLElement>("[aria-label='Collapse sidebar']")!.click();
		await flush();

		expect(state(host)).toBe("collapsed");
		expect(panel(host).hasAttribute("inert")).toBe(true);
		expect(JSON.parse(localStorage.getItem(STORE)!)).toEqual({ [READER]: true });

		// A fresh shell over the same browser comes up collapsed.
		const again = await shell();
		expect(state(again)).toBe("collapsed");

		again.querySelector<HTMLElement>("[aria-label='Expand sidebar']")!.click();
		await flush();
		expect(state(again)).toBe("expanded");
		expect(again.querySelector("[data-slot='sidebar']")!.hasAttribute("inert")).toBe(false);
	});
});

describe("whose collapse it is", () => {
	it("keeps one reader's collapse from another on the same browser", async () => {
		const host = await shell();
		host.querySelector<HTMLElement>("[aria-label='Collapse sidebar']")!.click();
		await flush();

		expect(state(await shell("colleague@example.com"))).toBe("expanded");
		expect(state(await shell())).toBe("collapsed");
	});

	it("takes over the collapse kept before it was per reader", async () => {
		localStorage.setItem("frappe:desk:sidebar-collapsed", "true");
		expect(state(await shell())).toBe("collapsed");
		expect(localStorage.getItem("frappe:desk:sidebar-collapsed")).toBeNull();
	});
});

describe("the seam", () => {
	it("collapses on a click", async () => {
		const host = await shell();
		seam(host).click();
		await flush();
		expect(state(host)).toBe("collapsed");
	});

	it("collapses on a drag toward the rail, and the drag's own click does not reopen it", async () => {
		const host = await shell();

		pointer(seam(host), "pointerdown", 300);
		pointer(window, "pointermove", 250);
		await flush();
		expect(state(host)).toBe("collapsed");

		pointer(window, "pointerup", 250);
		seam(host).click();
		await flush();
		expect(state(host)).toBe("collapsed");
	});

	it("ignores a drag that stops short", async () => {
		const host = await shell();

		pointer(seam(host), "pointerdown", 300);
		pointer(window, "pointermove", 280);
		pointer(window, "pointerup", 280);
		await flush();

		expect(state(host)).toBe("expanded");
	});
});
