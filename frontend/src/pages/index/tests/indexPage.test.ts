// The index page: one tile per boot app, the filter box, its states, and the keys it answers.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import type { Boot } from "@/boot";
import IndexPage from "../IndexPage.vue";

type BootApp = NonNullable<Boot["apps"]>[number];

const APPS: BootApp[] = [
	{ app: "frappe", title: "Framework", logo: "/assets/frappe/logo.svg", kind: "prefix", route: "/apps/desk" },
	{ app: "erpnext", title: "ERPNext", logo: null, kind: "prefix", route: "/apps/erpnext" },
	{ app: "crm", title: "CRM", logo: "/assets/crm/logo.svg", kind: "prefix", route: "/apps/crm" },
	{ app: "gameplan", title: "Gameplan", logo: null, kind: "link", route: "/g" },
];

const mounted: App[] = [];
let assign: ReturnType<typeof vi.fn>;

beforeEach(() => {
	assign = vi.fn();
	vi.stubGlobal("location", { ...window.location, assign });
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
});

async function mount(apps: BootApp[] = APPS) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(IndexPage);
	app.provide("boot", { app: null, apps } as unknown as Boot);
	app.mount(host);
	mounted.push(app);
	await nextTick();
	return host;
}

function box(host: HTMLElement) {
	return host.querySelector<HTMLInputElement>("input")!;
}

async function type(host: HTMLElement, text: string) {
	box(host).value = text;
	box(host).dispatchEvent(new Event("input"));
	await nextTick();
}

async function press(host: HTMLElement, key: string) {
	const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
	box(host).dispatchEvent(event);
	await nextTick();
	return event;
}

function tiles(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLAnchorElement>("a[data-app]")];
}

function selected(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLElement>("[data-selected]")].map((tile) => tile.dataset.app);
}

describe("the index page", () => {
	it("draws a tile per app in boot's order, each a link to where the app opens", async () => {
		const host = await mount();
		expect(tiles(host).map((tile) => [tile.dataset.app, tile.getAttribute("href")])).toEqual([
			["frappe", "/apps/desk"],
			["erpnext", "/apps/erpnext"],
			["crm", "/apps/crm"],
			["gameplan", "/g"],
		]);
		expect(tiles(host)[0].textContent?.trim()).toBe("Framework");
	});

	it("draws a logo lazily, and the title's first letter for an app with none", async () => {
		const host = await mount();
		const [framework, erpnext] = tiles(host);
		expect(framework.querySelector("img")?.getAttribute("loading")).toBe("lazy");
		expect(erpnext.querySelector("img")).toBeNull();
		expect(erpnext.querySelector("[data-app-logo]")?.textContent?.trim()).toBe("E");
	});

	it("draws the letter in place of a logo that fails to load", async () => {
		const host = await mount();
		const framework = tiles(host)[0];
		framework.querySelector("img")!.dispatchEvent(new Event("error"));
		await nextTick();
		expect(framework.querySelector("img")).toBeNull();
		expect(framework.querySelector("[data-app-logo]")?.textContent?.trim()).toBe("F");
	});

	it("has the filter box focused on load", async () => {
		const host = await mount();
		expect(document.activeElement).toBe(box(host));
	});

	it("filters the tiles by title, in any case", async () => {
		const host = await mount();
		await type(host, "  GAME ");
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["gameplan"]);
	});

	it("keeps the box as wide as all the apps' first row while it filters", async () => {
		const host = await mount();
		const width = box(host).parentElement!.className;
		await type(host, "crm");
		expect(box(host).parentElement!.className).toBe(width);
		expect(width).toContain("max-w-[440px]");
	});

	it("never makes the box narrower than three columns", async () => {
		const host = await mount(APPS.slice(0, 1));
		expect(box(host).parentElement!.className).toContain("max-w-[312px]");
	});

	it("selects the first match as you type, and nothing once the box is empty", async () => {
		const host = await mount();
		expect(selected(host)).toEqual([]);
		await type(host, "e");
		expect(selected(host)).toEqual(["frappe"]);
		await type(host, "");
		expect(selected(host)).toEqual([]);
	});

	it("opens the first match on Enter", async () => {
		const host = await mount();
		await type(host, "crm");
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/apps/crm");
	});

	it("opens the first tile on Enter with an empty box", async () => {
		const host = await mount();
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/apps/desk");
	});

	it("moves the selection with the arrow keys, and Enter opens it", async () => {
		const host = await mount();
		const first = await press(host, "ArrowDown");
		expect(first.defaultPrevented).toBe(true);
		expect(selected(host)).toEqual(["frappe"]);
		await press(host, "ArrowRight");
		await press(host, "ArrowRight");
		expect(selected(host)).toEqual(["crm"]);
		await press(host, "ArrowLeft");
		expect(selected(host)).toEqual(["erpnext"]);
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/apps/erpnext");
	});

	it("points the box at the selected tile, and scrolls it into view", async () => {
		const scroll = vi.fn();
		HTMLElement.prototype.scrollIntoView = scroll;
		const host = await mount();
		expect(box(host).getAttribute("aria-activedescendant")).toBeNull();
		await press(host, "ArrowRight");
		await press(host, "ArrowRight");
		const erpnext = tiles(host)[1];
		expect(box(host).getAttribute("aria-activedescendant")).toBe(erpnext.id);
		expect(erpnext.getAttribute("aria-selected")).toBe("true");
		expect(scroll.mock.contexts.at(-1)).toBe(erpnext);
	});

	it("clears the box on Esc", async () => {
		const host = await mount();
		await type(host, "zzz");
		await press(host, "Escape");
		expect(box(host).value).toBe("");
		expect(tiles(host)).toHaveLength(4);
		expect(selected(host)).toEqual([]);
	});

	it("says when nothing matches, and Clear brings every tile back", async () => {
		const host = await mount();
		await type(host, "zzz");
		const state = host.querySelector("[data-index-state='no-match']")!;
		expect(state.textContent).toContain("No app matches “zzz”.");
		expect(tiles(host)).toHaveLength(0);

		state.querySelector("button")!.click();
		await nextTick();
		expect(box(host).value).toBe("");
		expect(tiles(host)).toHaveLength(4);
		expect(document.activeElement).toBe(box(host));
	});

	it("says when the person can open no app", async () => {
		const host = await mount([]);
		expect(host.querySelector("[data-index-state='none']")?.textContent?.trim()).toBe(
			"No apps you can open yet."
		);
		await press(host, "Enter");
		expect(assign).not.toHaveBeenCalled();
	});
});
