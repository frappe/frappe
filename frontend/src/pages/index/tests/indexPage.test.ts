// The index page: one tile per boot app, the filter box, its states, and the keys it answers.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { pageMenuItems } from "@/shell/pageMenu";
import IndexPage from "../IndexPage.vue";
import IndexSkeleton from "../IndexSkeleton.vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	runMethod: fake.runMethod,
}));

type BootApp = NonNullable<Boot["apps"]>[number];

const APPS: BootApp[] = [
	{ app: "frappe", title: "Framework", logo: "/assets/frappe/logo.svg", kind: "prefix", route: "/apps/desk", hidden: false },
	{ app: "erpnext", title: "ERPNext", logo: null, kind: "prefix", route: "/apps/erpnext", hidden: false },
	{ app: "crm", title: "CRM", logo: "/assets/crm/logo.svg", kind: "prefix", route: "/apps/crm", hidden: false },
	{ app: "gameplan", title: "Gameplan", logo: null, kind: "link", route: "/g", hidden: false },
];

type BootFavourite = NonNullable<Boot["favourites"]>[number];

const FAVOURITES: BootFavourite[] = [
	{
		doctype: "CRM Deal",
		name: "CRM-DEAL-0001",
		kind: "record",
		title: "Globex Corporation",
		route: "/deal/CRM-DEAL-0001",
		app: "crm",
		app_title: "CRM",
		app_logo: "/assets/crm/logo.svg",
	},
	{
		doctype: "ToDo",
		name: "t1",
		kind: "record",
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

// The palette's server reads, answering nothing: this file tests the page, not its search.
const NOTHING_FOUND: Record<string, unknown> = {
	"frappe.shell.palette.places": { doctypes: [], apps: [], titles: {}, recent: [] },
	"frappe.shell.settings.get_panes": { panes: [], index: [], titles: {} },
};

const mounted: App[] = [];

// The search's chunk loads on the first keystroke; its first transform here outlasts a `waitFor`.
beforeAll(() => import("../indexSearch"), 60000);
let assign: ReturnType<typeof vi.fn>;

beforeEach(() => {
	fake.runMethod.mockReset().mockImplementation(async (method: string) => ({
		data: NOTHING_FOUND[method] ?? [],
	}));
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
	recent: BootVisit[] = [],
	moreApps: string | null = null,
	moreFavourites = false
) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(IndexPage);
	const session = { timezone: "Asia/Kolkata", user: { name: "reader@example.com" } };
	app.provide("boot", { app: null, apps, favourites, recent, more_apps: moreApps, more_favourites: moreFavourites, session, prefixes: {} } as unknown as Boot);
	app.provide("addresses", new Addresses({ doctypes: {}, modules: {}, singles: [] }));
	app.use(createRouter({ history: createMemoryHistory(), routes: [{ path: "/", component: {} }] }));
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

	it("says in one line when no tile and no row matches", async () => {
		const host = await mount();
		await type(host, "zzz");
		await vi.waitFor(() =>
			expect(host.querySelector("[data-index-state='no-match']")?.textContent?.trim()).toBe(
				"No results for “zzz”"
			)
		);
		expect(tiles(host)).toHaveLength(0);
		expect(host.querySelector("[data-index-state='no-match'] button")).toBeNull();
	});

	it("still says so above Ask Flow, which is offered for any text", async () => {
		document.documentElement.dataset.flow = "ready";
		try {
			const host = await mount();
			await type(host, "zzz");
			await vi.waitFor(() =>
				expect(host.querySelector("[data-index-state='no-match']")?.textContent?.trim()).toBe(
					"No results for “zzz”"
				)
			);
			expect(host.querySelector("[data-result='ask-flow']")).not.toBeNull();
		} finally {
			delete document.documentElement.dataset.flow;
		}
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

function favourite(number: number): BootFavourite {
	return {
		doctype: "ToDo",
		name: `t${number}`,
		kind: "record",
		title: `Task ${number}`,
		route: `/todo/t${number}`,
		app: "frappe",
		app_title: "Framework",
		app_logo: null,
	};
}

const LIST_AND_VIEW: BootFavourite[] = [
	{
		doctype: "DocType",
		name: "CRM Deal",
		kind: "list",
		title: "CRM Deal",
		route: "/crm/crm-deal",
		app: "crm",
		app_title: "CRM",
		app_logo: "/assets/crm/logo.svg",
	},
	{
		doctype: "Doctype View",
		name: "v1",
		kind: "view",
		title: "Open deals",
		route: "/crm/crm-deal/view/list/v1",
		app: "crm",
		app_title: "CRM",
		app_logo: "/assets/crm/logo.svg",
	},
];

describe("the index's Favourites past the first eight", () => {
	const EIGHT = Array.from({ length: 8 }, (_, number) => favourite(number + 1));
	const REST = [favourite(9), favourite(10)];

	beforeEach(() => {
		fake.runMethod.mockImplementation(async (method: string) => ({
			data: method === "frappe.shell.index_favourites.more_favourites" ? REST : NOTHING_FOUND[method] ?? [],
		}));
	});

	function more(host: HTMLElement) {
		return host.querySelector<HTMLButtonElement>("button[data-favourite='favourites:more']");
	}

	function moreCalls() {
		return fake.runMethod.mock.calls.filter(([method]) => method === "frappe.shell.index_favourites.more_favourites");
	}

	async function settle() {
		await new Promise((resolve) => setTimeout(resolve));
		await nextTick();
	}

	it("draws a list and a saved view as chips at their own addresses", async () => {
		const host = await mount(APPS, LIST_AND_VIEW);
		expect(chips(host).map((chip) => [chip.dataset.kind, chip.lastElementChild?.textContent, chip.getAttribute("href")])).toEqual([
			["list", "CRM Deal", "/crm/crm-deal"],
			["view", "Open deals", "/crm/crm-deal/view/list/v1"],
		]);
	});

	it("draws no More chip when boot has no favourites past the eighth", async () => {
		const host = await mount(APPS, EIGHT);
		expect(more(host)).toBeNull();
	});

	it("loads /apps with no request for the rest", async () => {
		await mount(APPS, EIGHT, [], null, true);
		expect(moreCalls()).toHaveLength(0);
	});

	it("draws More last; a click fetches the rest once, draws it under the eight and turns into Less", async () => {
		const host = await mount(APPS, EIGHT, [], null, true);
		expect(more(host)?.parentElement).toBe(host.querySelector("[data-index-favourites] ul")?.lastElementChild);
		expect(more(host)?.textContent?.trim()).toBe("More");

		more(host)!.click();
		await settle();
		expect(moreCalls()).toEqual([["frappe.shell.index_favourites.more_favourites", {}, { http: "GET" }]]);
		expect(chips(host).map((chip) => chip.getAttribute("href"))).toEqual([...EIGHT, ...REST].map((chip) => chip.route));
		expect(more(host)?.textContent?.trim()).toBe("Less");

		more(host)!.click();
		await settle();
		expect(chips(host)).toHaveLength(8);
		expect(more(host)?.textContent?.trim()).toBe("More");

		more(host)!.click();
		await settle();
		expect(chips(host)).toHaveLength(10);
		expect(moreCalls()).toHaveLength(1);
	});

	it("reaches More by the arrow keys, runs it with Enter, then reaches the rest, and Less keeps the selection", async () => {
		const host = await mount([], EIGHT, [], null, true);
		for (let step = 0; step < 9; step++) await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["favourites:more"]);
		expect(box(host).getAttribute("aria-activedescendant")).toBe(more(host)?.id);

		await press(host, "Enter");
		await settle();
		expect(more(host)?.textContent?.trim()).toBe("Less");
		await press(host, "ArrowUp");
		expect(selected(host)).toEqual(["favourite:ToDo:t10"]);
		await press(host, "ArrowDown");
		expect(selected(host)).toEqual(["favourites:more"]);

		await press(host, "Enter");
		await settle();
		expect(chips(host)).toHaveLength(8);
		expect(selected(host)).toEqual(["favourites:more"]);
		expect(assign).not.toHaveBeenCalled();
	});

	it("keeps More when the fetch fails, and fetches again on the next click", async () => {
		fake.runMethod.mockImplementationOnce(async () => {
			throw new Error("offline");
		});
		const host = await mount(APPS, EIGHT, [], null, true);
		more(host)!.click();
		await settle();
		expect(more(host)?.textContent?.trim()).toBe("More");
		expect(chips(host)).toHaveLength(8);

		more(host)!.click();
		await settle();
		expect(chips(host)).toHaveLength(10);
		expect(moreCalls()).toHaveLength(2);
	});

	it("ignores a second click while the rest is loading", async () => {
		const host = await mount(APPS, EIGHT, [], null, true);
		more(host)!.click();
		more(host)!.click();
		await settle();
		expect(moreCalls()).toHaveLength(1);
		expect(more(host)?.textContent?.trim()).toBe("Less");
	});

	it("draws no chip twice when the rest repeats one boot drew", async () => {
		fake.runMethod.mockImplementation(async () => ({ data: [EIGHT[7], ...REST] }));
		const host = await mount(APPS, EIGHT, [], null, true);
		more(host)!.click();
		await settle();
		expect(chips(host)).toHaveLength(10);
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

describe("the person's layer", () => {
	const HIDDEN_CRM = APPS.map((app) => ({ ...app, hidden: app.app === "crm" }));

	// The page loads it lazily; loaded here, a click draws it within one flush.
	beforeAll(() => import("../ArrangeApps.vue"));

	async function flush() {
		for (let tick = 0; tick < 5; tick++) await new Promise((resolve) => setTimeout(resolve));
		await nextTick();
	}

	async function openTileMenu(host: HTMLElement, app: string) {
		const tile = tiles(host).find((tile) => tile.dataset.app === app)!;
		const trigger = tile.parentElement!.querySelector<HTMLElement>("[data-tile-menu]")!;
		trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await flush();
		return [...document.body.querySelectorAll<HTMLElement>("[role='menuitem']")];
	}

	function saved() {
		return fake.runMethod.mock.calls.map(([method, args]) => [method, args]);
	}

	function arrangeGrid(host: HTMLElement) {
		return [...host.querySelectorAll<HTMLElement>("li[data-app]")].map((tile) => [
			tile.dataset.app,
			tile.querySelector("[data-eye]")!.getAttribute("aria-pressed"),
		]);
	}

	async function arrange(host: HTMLElement) {
		pageMenuItems.value.find((item) => item.label === "Arrange apps")!.onClick();
		await flush();
		return host.querySelector<HTMLElement>("[data-arrange-strip]")!;
	}

	function button(root: HTMLElement, label: string) {
		return [...root.querySelectorAll("button")].find((node) => node.textContent?.trim() === label)!;
	}

	it("leaves a hidden app out of the grid and the box's width, but the filter still finds it", async () => {
		const host = await mount(HIDDEN_CRM);
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["frappe", "erpnext", "gameplan"]);
		expect(box(host).parentElement!.className).toContain("max-w-[312px]");

		await type(host, "cr");
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["crm"]);
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith("/apps/crm");
	});

	it("hides a tile from its menu at once, and stores the layer", async () => {
		fake.runMethod.mockResolvedValue({ data: HIDDEN_CRM });
		const host = await mount();
		const [hide] = await openTileMenu(host, "crm");
		expect(hide.textContent?.trim()).toBe("Hide");

		hide.click();
		await flush();
		expect(tiles(host).map((tile) => tile.dataset.app)).not.toContain("crm");
		expect(saved()).toEqual([
			[
				"frappe.shell.boot.save_index_layer",
				{ order: ["frappe", "erpnext", "crm", "gameplan"], hidden: ["crm"] },
			],
		]);
	});

	it("puts back only the tile whose save failed", async () => {
		let failFirst!: (error: Error) => void;
		fake.runMethod
			.mockReturnValueOnce(new Promise((_resolve, reject) => (failFirst = reject)))
			.mockResolvedValue({ data: [] });
		const host = await mount();
		(await openTileMenu(host, "crm"))[0].click();
		await flush();
		(await openTileMenu(host, "gameplan"))[0].click();
		await flush();
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["frappe", "erpnext"]);

		failFirst(new Error("offline"));
		await flush();
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["frappe", "erpnext", "crm"]);
	});

	it("offers Show on a hidden app the filter found", async () => {
		fake.runMethod.mockResolvedValue({ data: APPS });
		const host = await mount(HIDDEN_CRM);
		await type(host, "crm");
		const [show] = await openTileMenu(host, "crm");
		expect(show.textContent?.trim()).toBe("Show");

		show.click();
		await flush();
		await type(host, "");
		expect(tiles(host).map((tile) => tile.dataset.app)).toContain("crm");
		expect(saved()[0][1]).toEqual({ order: ["frappe", "erpnext", "crm", "gameplan"], hidden: [] });
	});

	it("says so when every app is hidden, with a way to arrange them", async () => {
		const host = await mount(APPS.map((app) => ({ ...app, hidden: true })));
		const state = host.querySelector<HTMLElement>("[data-index-state='all-hidden']")!;
		expect(state.textContent).toContain("You have hidden every app.");

		button(state, "Arrange apps").click();
		await flush();
		expect(host.querySelector("[data-arrange-strip]")).not.toBeNull();
	});

	it("adds Arrange apps to the avatar menu while the index is drawn", async () => {
		await mount();
		expect(pageMenuItems.value.map((item) => item.label)).toEqual(["Arrange apps"]);
		mounted.splice(0).forEach((app) => app.unmount());
		expect(pageMenuItems.value).toEqual([]);

		await mount([]);
		expect(pageMenuItems.value).toEqual([]);
	});

	it("keeps the rows of a page that mounted before the last one unmounted", async () => {
		await mount();
		const [first] = mounted.splice(0);
		await mount();
		first.unmount();
		expect(pageMenuItems.value.map((item) => item.label)).toEqual(["Arrange apps"]);
	});

	it("steps Favourites and Recent aside while arranging", async () => {
		const host = await mount(APPS, FAVOURITES, RECENT);
		expect(host.querySelector("[data-index-recent]")).not.toBeNull();
		await arrange(host);
		expect(chips(host)).toHaveLength(0);
		expect(host.querySelector("[data-index-recent]")).toBeNull();
	});

	it("arranges every app, hidden ones too, and Done stores the draft", async () => {
		const host = await mount(HIDDEN_CRM);
		await type(host, "erp");
		const strip = await arrange(host);
		expect(box(host).value).toBe("");
		// The box and the strip span the drag grid of all four apps, not the three shown.
		expect(box(host).parentElement!.className).toContain("max-w-[440px]");
		expect(strip.className).toContain("max-w-[440px]");
		expect(strip.textContent).toContain("Drag to reorder. Click the eye to hide an app.");
		expect(arrangeGrid(host)).toEqual([
			["frappe", "false"],
			["erpnext", "false"],
			["crm", "true"],
			["gameplan", "false"],
		]);
		expect(tiles(host)).toHaveLength(0);

		host.querySelector<HTMLElement>("li[data-app='crm'] [data-eye]")!.click();
		host.querySelector<HTMLElement>("li[data-app='gameplan'] [data-eye]")!.click();
		await nextTick();
		const gameplanEye = host.querySelector<HTMLElement>("li[data-app='gameplan'] [data-eye]")!;
		expect(gameplanEye.getAttribute("aria-label")).toBe("Hide Gameplan");

		// Alt+Left moves an app one place, keeping focus on its eye; the first app stays first.
		gameplanEye.focus();
		gameplanEye.dispatchEvent(
			new KeyboardEvent("keydown", { key: "ArrowLeft", altKey: true, bubbles: true, cancelable: true })
		);
		await nextTick();
		expect(document.activeElement).toBe(host.querySelector("li[data-app='gameplan'] [data-eye]"));
		const frappeEye = host.querySelector<HTMLElement>("li[data-app='frappe'] [data-eye]")!;
		frappeEye.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", altKey: true, bubbles: true }));
		await nextTick();
		expect(arrangeGrid(host).map(([app]) => app)).toEqual(["frappe", "erpnext", "gameplan", "crm"]);

		const stored = [APPS[0], APPS[1], { ...APPS[3], hidden: true }, APPS[2]];
		fake.runMethod.mockResolvedValue({ data: stored });
		button(strip, "Done").click();
		await flush();

		expect(saved()).toEqual([
			[
				"frappe.shell.boot.save_index_layer",
				{ order: ["frappe", "erpnext", "gameplan", "crm"], hidden: ["gameplan"] },
			],
		]);
		expect(host.querySelector("[data-arrange-strip]")).toBeNull();
		expect(tiles(host).map((tile) => tile.dataset.app)).toEqual(["frappe", "erpnext", "crm"]);
		expect(document.activeElement).toBe(box(host));
	});

	it("spans the strip and the box over the drag grid's logos, three columns at least", async () => {
		const host = await mount(APPS.slice(0, 3));
		const strip = await arrange(host);
		expect(box(host).parentElement!.className).toContain("max-w-[312px]");
		expect(strip.className).toContain("max-w-[312px]");
		expect(strip.className).toContain("flex-wrap");
	});

	it("resets to the app layer and stays in arrange mode", async () => {
		const host = await mount(HIDDEN_CRM);
		const strip = await arrange(host);
		const appLayer = [APPS[2], APPS[0], APPS[1], APPS[3]];
		fake.runMethod.mockResolvedValue({ data: appLayer });

		button(strip, "Reset").click();
		await flush();

		expect(saved()).toEqual([["frappe.shell.boot.save_index_layer", { order: [], hidden: [] }]]);
		expect(arrangeGrid(host).map(([app, hidden]) => `${app}:${hidden}`)).toEqual([
			"crm:false",
			"frappe:false",
			"erpnext:false",
			"gameplan:false",
		]);
		expect(host.querySelector("[data-arrange-strip]")).not.toBeNull();
	});

	it("keeps the box and the strip on the drag grid when Reset returns fewer apps", async () => {
		const host = await mount(APPS);
		const strip = await arrange(host);
		fake.runMethod.mockResolvedValue({ data: APPS.slice(0, 3) });

		button(strip, "Reset").click();
		await flush();

		expect(arrangeGrid(host)).toHaveLength(3);
		expect(box(host).parentElement!.className).toContain("max-w-[312px]");
		expect(strip.className).toContain("max-w-[312px]");
	});

	it("stays in arrange mode with the draft when Done fails", async () => {
		const host = await mount(HIDDEN_CRM);
		const strip = await arrange(host);
		fake.runMethod.mockRejectedValue(new Error("offline"));
		button(strip, "Done").click();
		await flush();
		expect(host.querySelector("[data-arrange-strip]")).not.toBeNull();
		expect(arrangeGrid(host)).toHaveLength(4);
	});
});

describe("the index's Get more apps tile", () => {
	const CLOUD_SETTINGS = "/desk?cloud_settings=1";

	beforeAll(() => import("../ArrangeApps.vue"));

	function moreApps(host: HTMLElement) {
		return host.querySelector<HTMLAnchorElement>("a[data-more-apps]");
	}

	it("draws no tile when boot names no place to get apps", async () => {
		const host = await mount();
		expect(moreApps(host)).toBeNull();
	});

	it("draws the dashed tile after the last app, a link out to Cloud Settings", async () => {
		const host = await mount(APPS, [], [], CLOUD_SETTINGS);
		const items = [...host.querySelectorAll<HTMLAnchorElement>("ul[role='listbox'] a")];
		expect(items.at(-1)).toBe(moreApps(host));
		expect(moreApps(host)!.getAttribute("href")).toBe(CLOUD_SETTINGS);
		expect(moreApps(host)!.textContent?.trim()).toBe("Get more apps");
	});

	it("takes a column in the grid and in the box's width, which typing does not change", async () => {
		const host = await mount(APPS, [], [], CLOUD_SETTINGS);
		expect(host.querySelector("ul[role='listbox']")!.className).toContain("grid-cols-[repeat(5,112px)]");
		expect(box(host).parentElement!.className).toContain("max-w-[568px]");
		await type(host, "crm");
		expect(box(host).parentElement!.className).toContain("max-w-[568px]");
	});

	it("is counted in the loading state's box too, so the box does not jump at load", async () => {
		const host = document.createElement("div");
		document.body.appendChild(host);
		const skeleton = createApp(IndexSkeleton);
		skeleton.provide("boot", { app: null, apps: APPS, more_apps: CLOUD_SETTINGS } as unknown as Boot);
		skeleton.mount(host);
		mounted.push(skeleton);
		expect(host.querySelector("input")!.parentElement!.className).toContain("max-w-[568px]");
		expect(host.querySelector("[data-index-skeleton] .grid")!.className).toContain("grid-cols-[repeat(5,112px)]");
		expect(host.querySelector("[data-index-skeleton] .grid")!.children).toHaveLength(5);
	});

	it("never matches the filter", async () => {
		const host = await mount(APPS, [], [], CLOUD_SETTINGS);
		await type(host, "e");
		expect(moreApps(host)).toBeNull();
		await type(host, "get more");
		await vi.waitFor(() =>
			expect(host.querySelector("[data-index-state='no-match']")).not.toBeNull()
		);
		await press(host, "Escape");
		expect(moreApps(host)).not.toBeNull();
	});

	it("joins the arrow keys as the last tile, and Enter links out", async () => {
		const host = await mount(APPS, FAVOURITES, [], CLOUD_SETTINGS);
		for (let step = 0; step < 5; step++) await press(host, "ArrowRight");
		expect(moreApps(host)!.getAttribute("aria-selected")).toBe("true");
		expect(box(host).getAttribute("aria-activedescendant")).toBe(moreApps(host)!.id);
		await press(host, "ArrowRight");
		expect(selected(host)).toEqual(["favourite:CRM Deal:CRM-DEAL-0001"]);
		await press(host, "ArrowLeft");
		await press(host, "Enter");
		expect(assign).toHaveBeenCalledWith(CLOUD_SETTINGS);
	});

	it("is not in the arrange grid", async () => {
		const host = await mount(APPS, [], [], CLOUD_SETTINGS);
		pageMenuItems.value.find((item) => item.label === "Arrange apps")!.onClick();
		for (let tick = 0; tick < 5; tick++) await new Promise((resolve) => setTimeout(resolve));
		await nextTick();
		expect(host.querySelectorAll("li[data-app]")).toHaveLength(4);
		expect(moreApps(host)).toBeNull();
		expect(host.textContent).not.toContain("Get more apps");
	});
});
