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

type BootFavourite = NonNullable<Boot["favourites"]>[number];

const FAVOURITES: BootFavourite[] = [
	{
		doctype: "CRM Deal",
		name: "CRM-DEAL-0001",
		title: "Globex Corporation",
		route: "/deal/CRM-DEAL-0001",
		app: "crm",
		app_title: "CRM",
		app_logo: "/assets/crm/logo.svg",
	},
	{
		doctype: "ToDo",
		name: "t1",
		title: "Call Globex",
		route: "/todo/t1",
		app: "frappe",
		app_title: "Framework",
		app_logo: null,
	},
];

type BootVisit = NonNullable<Boot["recent"]>[number];

const RECENT: BootVisit[] = [
	{
		route: "/crm/crm-deal/CRM-DEAL-0001",
		title: "Globex Corporation",
		kind: "CRM Deal",
		visited: "2026-10-26 17:28:00.000000",
		app: "crm",
		app_title: "CRM",
		app_logo: "/assets/crm/logo.svg",
	},
	{
		route: "/desk/todo",
		title: "ToDo",
		kind: "List",
		visited: "2026-10-26 14:30:00.000000",
		app: "frappe",
		app_title: "Framework",
		app_logo: null,
	},
	{
		route: "/desk/system-settings/System%20Settings",
		title: "System Settings",
		kind: null,
		visited: "2026-10-25 17:30:00.000000",
		app: "frappe",
		app_title: "Framework",
		app_logo: null,
	},
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

async function mount(
	apps: BootApp[] = APPS,
	favourites: BootFavourite[] = [],
	recent: BootVisit[] = []
) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(IndexPage);
	const session = { timezone: "Asia/Kolkata" };
	app.provide("boot", { app: null, apps, favourites, recent, session } as unknown as Boot);
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
	return [...host.querySelectorAll<HTMLElement>("[data-selected]")].map(
		(item) => item.dataset.app ?? item.dataset.favourite ?? item.dataset.recent
	);
}

function chips(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLAnchorElement>("a[data-favourite]")];
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

describe("the index's Favourites", () => {
	it("draws no Favourites row when the person has none", async () => {
		const host = await mount(APPS, []);
		expect(host.querySelector("[data-index-favourites]")).toBeNull();
	});

	it("draws a chip per favourite under the tiles, in boot's order, each a link to its record", async () => {
		const host = await mount(APPS, FAVOURITES);
		const section = host.querySelector("[data-index-favourites]")!;
		expect(section.querySelector("h2")?.textContent?.trim()).toBe("Favourites");
		expect(host.querySelector("[data-index-favourites]")?.previousElementSibling?.id).toBe(
			"index-apps"
		);
		expect(chips(host).map((chip) => [chip.lastElementChild?.textContent, chip.getAttribute("href")])).toEqual([
			["Globex Corporation", "/deal/CRM-DEAL-0001"],
			["Call Globex", "/todo/t1"],
		]);
	});

	it("draws each chip with its app's logo, and the app's first letter for an app with none", async () => {
		const host = await mount(APPS, FAVOURITES);
		const [deal, todo] = chips(host);
		expect(deal.querySelector("img")?.getAttribute("src")).toBe("/assets/crm/logo.svg");
		expect(todo.querySelector("[data-app-logo]")?.textContent?.trim()).toBe("F");
	});

	it("steps aside while the box holds a query, and comes back when it is cleared", async () => {
		const host = await mount(APPS, FAVOURITES);
		await type(host, "crm");
		expect(chips(host)).toHaveLength(0);
		await press(host, "Escape");
		expect(chips(host)).toHaveLength(2);
	});

	it("joins the arrow keys: Down from the last row of tiles reaches the first chip", async () => {
		const host = await mount(APPS, FAVOURITES);
		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["frappe"]);
		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["favourite:CRM Deal:CRM-DEAL-0001"]);
		await press(host, "ArrowRight");
		expect(selected(host)).toEqual(["favourite:ToDo:t1"]);
		const todo = chips(host)[1];
		expect(todo.getAttribute("aria-selected")).toBe("true");
		expect(box(host).getAttribute("aria-activedescendant")).toBe(todo.id);
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/todo/t1");
	});

	it("moves through wrapped chips with Down, and back up from the first chip to the last tile", async () => {
		const host = await mount(APPS, FAVOURITES);
		await press(host, "ArrowDown");
		await press(host, "ArrowDown");
		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["favourite:ToDo:t1"]);
		await press(host, "ArrowUp");
		await press(host, "ArrowUp");
		expect(selected(host)).toEqual(["gameplan"]);
	});

	it("names the Favourites listbox as one the box controls while it is drawn", async () => {
		const host = await mount(APPS, FAVOURITES);
		const list = host.querySelector("[data-index-favourites] [role='listbox']")!;
		expect(box(host).getAttribute("aria-controls")).toBe(`index-apps ${list.id}`);
		await type(host, "zzz");
		expect(box(host).getAttribute("aria-controls")).toBeNull();
		expect(box(host).getAttribute("aria-expanded")).toBe("false");
	});

	it("draws the Favourites row when the person can open no app", async () => {
		const host = await mount([], FAVOURITES);
		expect(chips(host)).toHaveLength(2);
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/deal/CRM-DEAL-0001");
	});
});

describe("the index's Recent", () => {
	beforeEach(() => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
	});

	afterEach(() => vi.useRealTimers());

	function rows(host: HTMLElement) {
		return [...host.querySelectorAll<HTMLAnchorElement>("a[data-recent]")];
	}

	it("draws no Recent section when the person has visited nothing", async () => {
		const host = await mount(APPS, FAVOURITES, []);
		expect(host.querySelector("[data-index-recent]")).toBeNull();
	});

	it("draws a row per visit after Favourites, each with its logo, title, kind, time and address", async () => {
		const host = await mount(APPS, FAVOURITES, RECENT);
		const section = host.querySelector("[data-index-recent]")!;
		expect(section.querySelector("h2")?.textContent?.trim()).toBe("Recent");
		expect(section.previousElementSibling?.hasAttribute("data-index-favourites")).toBe(true);
		expect(
			rows(host).map((row) => [
				[...row.querySelectorAll("[data-slot='item-label'] span span")]
					.map((part) => part.textContent?.trim())
					.join(" | "),
				row.querySelector("[data-slot='item-suffix']")?.textContent?.trim(),
				row.getAttribute("href"),
			])
		).toEqual([
			["Globex Corporation | CRM Deal", "2 minutes ago", "/crm/crm-deal/CRM-DEAL-0001"],
			["ToDo | List", "3 hours ago", "/desk/todo"],
			["System Settings", "a day ago", "/desk/system-settings/System%20Settings"],
		]);
		const [deal, todo] = rows(host);
		expect(deal.querySelector("img")?.getAttribute("src")).toBe("/assets/crm/logo.svg");
		expect(todo.querySelector("[data-app-logo]")?.textContent?.trim()).toBe("F");
	});

	it("steps aside while the box holds a query", async () => {
		const host = await mount(APPS, [], RECENT);
		await type(host, "crm");
		expect(rows(host)).toHaveLength(0);
		await press(host, "Escape");
		expect(rows(host)).toHaveLength(3);
	});

	it("joins the arrow keys after the last chip, one row at a time, and Enter opens the row", async () => {
		const host = await mount(APPS, FAVOURITES, RECENT);
		for (let step = 0; step < 4; step++) await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["recent:0"]);
		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["recent:1"]);
		const todo = rows(host)[1];
		expect(todo.getAttribute("aria-selected")).toBe("true");
		expect(box(host).getAttribute("aria-activedescendant")).toBe(todo.id);
		await press(host, "ArrowUp");
		await press(host, "ArrowUp");
		expect(selected(host)).toEqual(["favourite:ToDo:t1"]);
		await press(host, "ArrowDown");
		await press(host, "ArrowDown");
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/desk/todo");
	});

	it("names the Recent listbox as one the box controls while it is drawn", async () => {
		const host = await mount(APPS, FAVOURITES, RECENT);
		expect(box(host).getAttribute("aria-controls")).toBe(
			"index-apps index-favourites index-recent"
		);
		await type(host, "zzz");
		expect(box(host).getAttribute("aria-controls")).toBeNull();
	});
});
