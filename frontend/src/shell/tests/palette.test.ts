// The command palette in the shell: Mod+K and the rail open it, its groups read the acts
// available now, and a picked row runs through the dispatcher.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { acts, type ActEntry, type ActScope } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { installTranslate } from "@/i18n";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { standardPages } from "@/pages/standardPages";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { paletteOpen, registerPageRows, type PaletteRow } from "../palette";
import { pinnedRows } from "../paletteGroups";
import { recents } from "../recents";

registerStandardPages(standardPages);

const server = vi.hoisted(() => ({ runMethod: vi.fn(), searchDocuments: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
	runMethod: server.runMethod,
	searchDocuments: server.searchDocuments,
}));

// The prefixes the server's addresses sit under, as `canonical_path` writes them.
const crmBase = "/apps/crm";
const deskBase = "/apps/desk";

const probes = Array.from({ length: 10 }, (_, index) => ({
	name: `Probe ${index}`,
	app: "crm",
	route: `${crmBase}/probe-${index}`,
	single: false,
	can_create: true,
}));

/** What `frappe.shell.palette.places` answers: read once, so one reply serves every test. */
const placesReply = {
	doctypes: [
		{ name: "CRM Deal", app: "crm", route: `${crmBase}/crm-deal`, single: false, can_create: true },
		{ name: "CRM Lead", app: "crm", route: `${crmBase}/crm-lead`, single: false, can_create: false },
		{
			name: "System Settings",
			app: "frappe",
			route: `${deskBase}/system-settings/System Settings`,
			single: true,
			can_create: false,
		},
		{ name: "ToDo", app: "frappe", route: `${deskBase}/todo`, single: false, can_create: true },
		...probes,
	],
	apps: [
		{ app: "crm", title: "CRM", route: crmBase },
		{ app: "frappe", title: "Desk", route: deskBase },
	],
	titles: { crm: "CRM", frappe: "Desk" },
};

const panesReply = {
	panes: [{ app: "frappe", key: "users", label: "Users", blocks: [] }],
	index: [],
	titles: { frappe: "Desk" },
};

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"CRM Lead": ["crm-lead", "fcrm"],
		ToDo: ["todo", "desk"],
	},
	modules: { fcrm: "FCRM", desk: "Desk" },
});

const deals: NavigationItem = {
	key: "deals",
	item_type: "DocType",
	link_to: "CRM Deal",
	label: "Deals",
};

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false }, desk: { app: "frappe", modular: false } },
	navigation: { rail: [deals], sidebars: {} },
	session: {
		user: { name: "reader@example.com", full_name: "Reader", email: "reader@example.com" },
	},
} as unknown as Boot;

const page = { render: () => null };
const releases: (() => void)[] = [];
const ran: string[] = [];

async function flush() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function shell(path = "/crm-deal", shellBoot: Boot = boot): Promise<Router> {
	const router = createRouter({
		history: createMemoryHistory(shellBoot.shell_base),
		routes: [
			{ path: "/", name: "home", component: page },
			{ path: "/:doctype", name: "list", component: page },
			{ path: "/:doctype/:name", name: "record", component: page },
		],
	});
	registerShell({ boot: shellBoot, addresses, router });
	recents.track(router, shellBoot, addresses);

	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(AppShell);
	installTranslate(app);
	app.provide("boot", shellBoot);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push(path);
	await router.isReady();
	app.mount(host);
	releases.push(() => app.unmount());
	// Mod+K is bound by a lazy component; a test presses once it is in.
	await import("../paletteKey");
	await flush();
	return router;
}

function register(surfaces: Record<string, ActEntry[]>) {
	const scope: ActScope = {
		surfaces: Object.fromEntries(
			Object.entries(surfaces).map(([name, entries]) => [name, () => entries])
		),
		context: () => ({}),
		passes: (right) => right !== "delete",
		settled: () => undefined,
		hold: async (work) => work(),
		failed: () => {},
	};
	releases.push(acts.register(scope));
}

function act(name: string, label: string, extra: Partial<ActEntry["item"]> = {}): ActEntry {
	return { item: { name, label, run: () => void ran.push(name), ...extra }, hidden: false };
}

/** The keydown, so a test can ask whether the browser's own Mod+K was stopped. */
function pressModK(target: EventTarget = document) {
	const mac = /Mac|iPhone|iPad/i.test(navigator.platform);
	const event = new KeyboardEvent("keydown", {
		key: "k",
		ctrlKey: !mac,
		metaKey: mac,
		bubbles: true,
		cancelable: true,
	});
	target.dispatchEvent(event);
	return event;
}

async function open() {
	pressModK();
	await vi.waitFor(() => expect(input()).not.toBeNull(), { timeout: 10000 });
	await flush();
}

function input() {
	return document.body.querySelector<HTMLInputElement>("[data-slot='command-palette-input'] input");
}

async function type(text: string) {
	const field = input()!;
	field.value = text;
	field.dispatchEvent(new Event("input", { bubbles: true }));
	await flush();
}

/** Each group's heading and its rows' labels, in the order drawn. */
function drawn() {
	return Array.from(document.body.querySelectorAll("[data-slot='command-palette-group']")).map(
		(group) => [
			group.querySelector("[data-slot='command-palette-group-label']")?.textContent?.trim(),
			...Array.from(group.querySelectorAll("[data-slot='command-palette-item-label']")).map(
				(label) => label.textContent?.replace(/\s+/g, " ").trim()
			),
		]
	);
}

async function press(key: string) {
	input()!.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
	await flush();
}

function row(id: string) {
	return document.body.querySelector<HTMLElement>(`[data-row='${CSS.escape(id)}']`);
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	server.runMethod.mockImplementation(async (method: string) => ({
		data: method === "frappe.shell.palette.places" ? placesReply : panesReply,
	}));
	server.searchDocuments.mockReset();
	document.body.innerHTML = "";
	localStorage.clear();
	paletteOpen.value = false;
	ran.length = 0;
	resetNavigationReports();
	resetSprite();
});

afterEach(() => {
	releases.splice(0).forEach((release) => release());
	pinnedRows.splice(0);
});

describe("opening the palette", () => {
	it("opens on Mod+K, and adds nothing to the address", async () => {
		const router = await shell();
		const pressed = pressModK();
		await vi.waitFor(() => expect(input()).not.toBeNull(), { timeout: 10000 });

		expect(pressed.defaultPrevented).toBe(true);
		expect(paletteOpen.value).toBe(true);
		expect(router.currentRoute.value.fullPath).toBe("/crm-deal");
	});

	it("opens on Mod+K from inside a field", async () => {
		await shell();
		const field = document.createElement("input");
		document.body.appendChild(field);

		pressModK(field);
		await flush();

		expect(paletteOpen.value).toBe(true);
	});

	it("leaves Mod+K to the rich-text editor", async () => {
		await shell();
		const editor = document.createElement("div");
		editor.className = "ProseMirror";
		editor.contentEditable = "true";
		document.body.appendChild(editor);

		const pressed = pressModK(editor);
		await flush();

		expect(pressed.defaultPrevented).toBe(false);
		expect(paletteOpen.value).toBe(false);
	});

	it("draws the acts of a page that registers while it is open", async () => {
		await shell();
		await open();
		expect(drawn()).toEqual([["Recent", "CRM Deal CRM"]]);

		register({ header: [act("save", "Save")] });
		await flush();

		expect(drawn()).toEqual([["Recent", "CRM Deal CRM"], ["This page", "Save"]]);
	});

	it("opens from the rail's search item", async () => {
		await shell();
		document.body.querySelector<HTMLElement>("[data-key='palette-trigger']")!.click();
		await vi.waitFor(() => expect(input()).not.toBeNull(), { timeout: 10000 });
	});
});

describe("the groups", () => {
	beforeEach(() => {
		register({
			header: [
				act("save", "Save", { key: "Mod+S", icon: "lucide-save" }),
				act("delete_all", "Delete all", { right: "delete" }),
				act("secret", "Secret", { palette: false }),
				{ ...act("gone", "Gone"), hidden: true },
				act("assign", "Assign to…", { argument: { label: "User", options: () => [] } }),
			],
			quickActions: [act("email", "Send an email")],
		});
		releases.push(
			registerPageRows(() => [
				{ id: "tab:activity", label: "Go to tab: Activity", run: () => ran.push("tab") },
			])
		);
	});

	it("shows Recent and This page on the empty query, and no Desk", async () => {
		const router = await shell("/crm-lead");
		await router.push("/crm-deal/DEAL-1");
		await router.push("/crm-deal");
		await open();

		expect(drawn()).toEqual([
			["Recent", "CRM Deal CRM", "DEAL-1 CRM Deal", "CRM Lead CRM"],
			["This page", "Save", "Send an email", "Go to tab: Activity"],
		]);
	});

	it("draws an act's key on the right", async () => {
		await shell();
		await open();

		expect(row("act:header.save")!.querySelector("[data-slot='keyboard-shortcut']")).not.toBeNull();
	});

	it("shows Recent five at most", async () => {
		const router = await shell("/todo");
		for (let index = 1; index <= 7; index++) await router.push("/todo/T-" + index);
		await open();

		expect(drawn()[0]).toEqual(["Recent", "T-7 ToDo", "T-6 ToDo", "T-5 ToDo", "T-4 ToDo", "T-3 ToDo"]);
	});

	it("ranks a typed query in This page, Desk with an app act's app, Go to, then Create", async () => {
		await shell();
		// After the shell, so this surface takes `shell` over from the shell's own acts.
		register({
			shell: [act("toggle_sidebar", "Toggle sidebar"), act("crm.log_a_call", "Log a call")],
		});
		await open();
		await type("s");

		expect(drawn()).toEqual([
			["This page", "Save", "Send an email"],
			["Desk", "Toggle sidebar"],
			["Go to", "System Settings Desk", "Users Desk", "Deals CRM", "Desk", "ToDo Desk"],
			["Create", "New ToDo Desk"],
		]);

		await type("crm");
		expect(drawn()).toEqual([
			["Desk", "Log a call CRM"],
			[
				"Go to",
				"CRM Deal CRM",
				"Deals CRM",
				"CRM",
				"CRM Lead CRM",
				"Probe 0 CRM",
				"Probe 1 CRM",
				"Probe 2 CRM",
				"Probe 3 CRM",
			],
			["Create", "New CRM Deal CRM", "New Probe 0 CRM", "New Probe 1 CRM", "New Probe 2 CRM", "New Probe 3 CRM"],
		]);
	});

	it("draws the shell's own acts in Desk, but not Create or Theme until they can ask for a value", async () => {
		await shell("/crm-deal");
		await open();

		await type("sidebar");
		expect(drawn()).toEqual([["Desk", "Customize sidebar"]]);
		await type("log");
		expect(drawn()).toEqual([["Desk", "Log out"]]);
		for (const query of ["create", "theme"]) {
			await type(query);
			expect(drawn()).toEqual([]);
		}
	});

	it("never draws a denied, hidden, opted-out or argument act", async () => {
		await shell();
		await open();

		for (const query of ["delete", "gone", "secret", "assign"]) {
			await type(query);
			expect(drawn()).toEqual([]);
		}
		expect(document.body.querySelector("[data-slot='command-palette-empty']")?.textContent).toContain(
			"No results for “assign”"
		);
	});

	it("runs a picked act through the dispatcher and closes", async () => {
		await shell();
		await open();
		await type("send");

		row("act:quickActions.email")!.click();
		await flush();

		expect(ran).toEqual(["email"]);
		expect(paletteOpen.value).toBe(false);
	});

	it("goes to a picked recent", async () => {
		const router = await shell("/crm-deal/DEAL-1");
		await router.push("/crm-lead");
		await open();

		row(`recent:${router.resolve("/crm-deal/DEAL-1").href}`)!.click();
		await flush();

		expect(router.currentRoute.value.fullPath).toBe("/crm-deal/DEAL-1");
	});
});

describe("a recent of another prefix", () => {
	/** A recent kept under another app's prefix, as that app's own shell would keep it. */
	async function keptElsewhere() {
		const elsewhere = { ...boot, app: "helpdesk", shell_base: boot.shell_base.replace("crm", "helpdesk") };
		const router = createRouter({
			history: createMemoryHistory(elsewhere.shell_base),
			routes: [{ path: "/:doctype/:name", name: "record", component: page }],
		});
		recents.track(router, elsewhere, addresses);
		await router.push("/todo/T-1");
		return router.resolve("/todo/T-1").href;
	}

	it("loads the other prefix's document, not a route of this one", async () => {
		const href = await keptElsewhere();
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const router = await shell();
		await open();

		row(`recent:${href}`)!.click();
		await flush();

		expect(assign).toHaveBeenCalledWith(href);
		expect(router.currentRoute.value.fullPath).toBe("/crm-deal");
		assign.mockRestore();
	});

	it("loads it from the index, which has no app routes", async () => {
		const href = await keptElsewhere();
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const index = { ...boot, app: null, app_title: undefined, shell_base: boot.shell_base.replace("/crm", "") };
		await shell("/", index as unknown as Boot);
		await open();

		row(`recent:${href}`)!.click();
		await flush();

		expect(assign).toHaveBeenCalledWith(href);
		assign.mockRestore();
	});
});

describe("places", () => {
	/** Takes the shell surface over, so a picked row's shell act is recorded with its value. */
	function recordShellActs() {
		const values: unknown[] = [];
		const record = (name: string) =>
			act(name, name, { run: (_context: unknown, value: unknown) => void values.push([name, value]) });
		register({ shell: [record("create"), record("open_settings")] });
		return values;
	}

	it("reads the places once in the tab, however often it opens", async () => {
		await shell();
		await open();
		paletteOpen.value = false;
		await flush();
		await open();

		const asked = server.runMethod.mock.calls.filter(([method]) => method === "frappe.shell.palette.places");
		// The module holds the reply for the tab, so this counts every open in this file.
		expect(asked).toHaveLength(1);
	});

	it("goes to a sidebar row, a doctype, and New X for a doctype the user may create", async () => {
		await shell("/todo");
		await open();
		await type("deal");

		expect(drawn()).toEqual([
			["Go to", "Deals CRM", "CRM Deal CRM"],
			["Create", "New CRM Deal CRM"],
		]);
	});

	it("offers no New X for a doctype the user may only read, nor for a single", async () => {
		await shell("/todo");
		await open();

		await type("lead");
		expect(drawn()).toEqual([["Go to", "CRM Lead CRM"]]);
		await type("system");
		expect(drawn()).toEqual([["Go to", "System Settings Desk"]]);
	});

	it("routes to a doctype in this prefix and loads one under another app's prefix", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const router = await shell("/todo");
		await open();
		await type("lead");
		row("doctype:CRM Lead")!.click();
		await flush();
		expect(router.currentRoute.value.fullPath).toBe("/crm-lead");

		await open();
		await type("todo");
		row("doctype:ToDo")!.click();
		await flush();
		expect(assign).toHaveBeenCalledWith(`${deskBase}/todo`);
		assign.mockRestore();
	});

	it("opens an app", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		await shell();
		await open();
		await type("desk");

		row("app:frappe")!.click();
		await flush();

		expect(assign).toHaveBeenCalledWith(deskBase);
		assign.mockRestore();
	});

	it("runs shell.create for New X and shell.open_settings for a settings pane", async () => {
		await shell();
		const values = recordShellActs();
		await open();

		await type("new crm deal");
		row("create:CRM Deal")!.click();
		await flush();
		await open();
		await type("users");
		row("settings:desk/users")!.click();
		await flush();

		expect(values).toEqual([
			["create", "CRM Deal"],
			["open_settings", { prefix: "desk", pane: "users" }],
		]);
	});
});

describe("Tab on a doctype row", () => {
	async function narrowToDeals() {
		const router = await shell("/todo");
		await open();
		await type("deal");
		expect(row(`sidebar:${crmBase}/crm-deal`)!.dataset.state).toBe("active");
		await press("Tab");
		return router;
	}

	function chip() {
		return document.body.querySelector("[data-slot='palette-scope-chip']");
	}

	function empty() {
		return document.body.querySelector("[data-slot='command-palette-empty']")?.textContent?.trim();
	}

	function footer() {
		return document.body.querySelector("[data-slot='command-palette-footer']")?.textContent ?? "";
	}

	function deal(name: string, label: string) {
		return { value: name, label, description: "" };
	}

	it("says Tab searches in the active row's doctype", async () => {
		await shell("/todo");
		await open();
		await type("deal");

		expect(footer()).toContain("to search in CRM Deal");
		await type("system");
		expect(footer()).not.toContain("to search in");
	});

	it("narrows the palette to the doctype, with a chip and an empty query", async () => {
		await narrowToDeals();

		expect(chip()?.textContent).toContain("in CRM Deal");
		expect(input()!.value).toBe("");
		expect(input()!.placeholder).toBe("Search CRM Deal");
		expect(drawn()).toEqual([]);
		expect(empty()).toBe("Type to search CRM Deal");
		expect(footer()).toContain("back");
	});

	it("searches the doctype after a pause, from two characters, and Enter opens the record", async () => {
		server.searchDocuments.mockResolvedValue({ data: [deal("DEAL-3", "PivotTech Solutions")] });
		const router = await narrowToDeals();

		await type("p");
		expect(empty()).toBe("Type to search CRM Deal");
		await type("pi");
		expect(drawn()).toEqual([["Records", "Searching…"]]);
		await type("piv");
		await vi.waitFor(() => expect(drawn()).toEqual([["Records", "PivotTech Solutions DEAL-3"]]));

		expect(server.searchDocuments).toHaveBeenCalledTimes(1);
		expect(server.searchDocuments).toHaveBeenCalledWith(
			"CRM Deal",
			{ txt: "piv", filters: {}, limit: 10 },
			{}
		);
		// The keyboard was on "Searching…", which cannot be picked; the record takes it.
		await vi.waitFor(() => expect(row("record:CRM Deal/DEAL-3")!.dataset.state).toBe("active"));
		await press("Enter");
		expect(router.currentRoute.value.fullPath).toBe("/crm-deal/DEAL-3");
	});

	it("drops an answer to an older query", async () => {
		let answerFirst: (value: unknown) => void = () => {};
		server.searchDocuments
			.mockImplementationOnce(() => new Promise((resolve) => (answerFirst = resolve)))
			.mockResolvedValueOnce({ data: [deal("DEAL-5", "Meridian Systems")] });
		await narrowToDeals();

		await type("pi");
		await vi.waitFor(() => expect(server.searchDocuments).toHaveBeenCalledTimes(1));
		await type("me");
		await vi.waitFor(() => expect(drawn()).toEqual([["Records", "Meridian Systems DEAL-5"]]));
		answerFirst({ data: [deal("DEAL-3", "PivotTech Solutions")] });
		await flush();

		expect(drawn()).toEqual([["Records", "Meridian Systems DEAL-5"]]);
	});

	it("leaves the scope on Backspace in an empty input, and on Esc without closing", async () => {
		await narrowToDeals();
		await press("Backspace");
		expect(chip()).toBeNull();
		expect(input()!.placeholder).toBe("Search or run an action");

		await type("deal");
		await press("Tab");
		await press("Escape");
		expect(chip()).toBeNull();
		expect(paletteOpen.value).toBe(true);
	});

	it("leaves the scope by the chip's ×, and when the palette closes", async () => {
		await narrowToDeals();
		chip()!.querySelector("button")!.click();
		await flush();
		expect(chip()).toBeNull();

		await type("deal");
		await press("Tab");
		paletteOpen.value = false;
		await flush();
		await open();
		expect(chip()).toBeNull();
	});
});

describe("the pinned area", () => {
	it("draws pinned rows in a second list the arrow keys reach", async () => {
		register({ header: [act("save", "Save")] });
		const pinned: PaletteRow = { id: "pinned", label: "Pinned row", run: () => ran.push("pinned") };
		pinnedRows.push(() => [pinned]);
		await shell();
		await open();

		const list = document.body.querySelector("[data-slot='palette-pinned']");
		expect(list?.textContent).toContain("Pinned row");

		await press("ArrowDown");
		expect(row("act:header.save")!.dataset.state).toBe("active");
		await press("ArrowDown");
		expect(row("pinned")!.dataset.state).toBe("active");

		await press("Enter");
		expect(ran).toEqual(["pinned"]);
	});

	it("draws no second list while nothing is pinned", async () => {
		await shell();
		await open();

		expect(document.body.querySelector("[data-slot='palette-pinned']")).toBeNull();
	});
});
