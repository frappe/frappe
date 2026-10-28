// The command palette in the shell: Mod+K and the rail open it, its groups read the acts
// available now, and a picked row runs through the dispatcher.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { getMeta } from "@framework/ui/api";
import { resetDoctypeMeta, useDoctypeMeta } from "@framework/ui/useDoctypeMeta";

import { acts, type ActArgument, type ActEntry, type ActOption, type ActScope } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { installTranslate } from "@/i18n";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { headerMenuBuiltins, quickActionBuiltins } from "@/pages/record/builtinActions";
import { FILES_TAB, recordTabBuiltins } from "@/pages/record/tabs/recordTabs";
import { standardPages } from "@/pages/standardPages";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { closeCreates, createRequests, registerCreateDialog } from "../create";
import { openArgumentStep, paletteOpen, registerPageRows, type PaletteRow } from "../palette";
import { pinnedRows } from "../paletteGroups";
import { recentVisits } from "../recentVisits";

registerStandardPages(standardPages);

const server = vi.hoisted(() => ({
	runMethod: vi.fn(),
	searchRecords: vi.fn(),
	searchDoctypeRecords: vi.fn(),
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
	getMeta: vi.fn(),
	runMethod: server.runMethod,
}));

const searchRecords = server.searchRecords;
const builtInPinned = pinnedRows.length;

// The prefixes the server's addresses sit under, as `canonical_path` writes them.
const crmBase = "/apps/crm";
const deskBase = "/apps/desk";

const probes = Array.from({ length: 10 }, (_, index) => ({
	name: `Probe ${index}`,
	app: "crm",
	route: `${crmBase}/probe-${index}`,
	can_create: true,
}));

/** What `frappe.shell.palette.places` answers: read once, so one reply serves every test. */
const placesReply = {
	doctypes: [
		{ name: "CRM Deal", app: "crm", route: `${crmBase}/crm-deal`, can_create: true },
		{ name: "CRM Lead", app: "crm", route: `${crmBase}/crm-lead`, can_create: false },
		{
			name: "System Settings",
			app: "frappe",
			route: `${deskBase}/system-settings/System Settings`,
			can_create: false,
		},
		{ name: "ToDo", app: "frappe", route: `${deskBase}/todo`, can_create: true },
		...probes,
	],
	apps: [
		{ app: "crm", title: "CRM", route: crmBase },
		{ app: "frappe", title: "Desk", route: deskBase },
	],
	titles: { crm: "CRM", frappe: "Desk" },
	// `Route History` as the server reads it: a deal this tab also visits, and a task under another prefix.
	recent: [
		{ route: `${crmBase}/crm-deal/DEAL-1`, doctype: "CRM Deal", name: "DEAL-1", title: "Acme deal", kind: "record", description: "CRM Deal", visited: 2 },
		{ route: `${deskBase}/todo/T-9`, doctype: "ToDo", name: "T-9", title: "Call back Acme", kind: "record", description: "ToDo", visited: 1 },
	],
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
		"System Settings": ["system-settings", "core"],
	},
	modules: { fcrm: "FCRM", desk: "Desk", core: "Core" },
	singles: ["System Settings"],
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
		// The index has no doctype routes.
		routes: [
			{ path: "/", name: "home", component: page },
			...(shellBoot.app
				? [
						{ path: "/:doctype", name: "list", component: page },
						{ path: "/:doctype/:name", name: "record", component: page },
				  ]
				: []),
		],
	});
	registerShell({ boot: shellBoot, addresses, router });
	recentVisits.track(router, shellBoot, addresses);

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

/** Types into the field, and lets the record search answer unless asked not to. */
async function type(text: string, { settle = true } = {}) {
	const field = input()!;
	field.value = text;
	field.dispatchEvent(new Event("input", { bubbles: true }));
	await flush();
	if (settle && row("records:searching"))
		await vi.waitFor(() => expect(row("records:searching")).toBeNull());
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

/** A row's gray text. */
function description(drawnRow: HTMLElement) {
	return drawnRow.querySelector("[data-slot='palette-description']")?.textContent?.trim() ?? "";
}

function row(id: string) {
	return document.body.querySelector<HTMLElement>(`[data-row='${CSS.escape(id)}']`);
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	server.runMethod.mockImplementation(async (method: string, ...rest: unknown[]) => {
		if (method === "frappe.desk.palette.search_records") return searchRecords(method, ...rest);
		if (method === "frappe.desk.palette.search_doctype_records")
			return server.searchDoctypeRecords(method, ...rest);
		return { data: method === "frappe.shell.palette.places" ? placesReply : panesReply };
	});
	server.searchDoctypeRecords.mockReset();
	document.body.innerHTML = "";
	localStorage.clear();
	paletteOpen.value = false;
	ran.length = 0;
	resetNavigationReports();
	resetSprite();
	resetDoctypeMeta();
	searchRecords.mockReset().mockResolvedValue({ data: [] });
	vi.mocked(getMeta).mockReset().mockRejectedValue(new Error("no meta in this test"));
});

afterEach(async () => {
	// Closing tells the record search, a module of its own, to forget the last question.
	paletteOpen.value = false;
	await nextTick();
	releases.splice(0).forEach((release) => release());
	pinnedRows.splice(builtInPinned);
	delete document.documentElement.dataset.flow;
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
		expect(drawn()).toEqual([["Recent", "CRM Deal CRM", "Acme deal CRM Deal", "Call back Acme ToDo"]]);

		register({ header: [act("save", "Save")] });
		await flush();

		expect(drawn()).toEqual([
			["Recent", "CRM Deal CRM", "Acme deal CRM Deal", "Call back Acme ToDo"],
			["This page", "Save"],
		]);
	});

	it("opens from the rail's search item", async () => {
		await shell();
		document.body.querySelector<HTMLElement>("[data-key='palette-trigger']")!.click();
		await vi.waitFor(() => expect(input()).not.toBeNull(), { timeout: 10000 });
	});
});

describe("This page on a record page", () => {
	it("draws one row per act: the star, not its menu copy, and Attach, not the Files tab's entry", async () => {
		const shown = (item: ActEntry["item"]): ActEntry => ({ item, hidden: false });
		const files = recordTabBuiltins({ requestUpload: () => {} }).find((tab) => tab.name === FILES_TAB)!;
		register({
			header: [
				act("favourite", "Favourite", { icon: "lucide-star" }),
				...headerMenuBuiltins({}, { favourited: false, toggle: () => {} }).map(shown),
			],
			quickActions: quickActionBuiltins({}, true, undefined, files.create).map(shown),
			tabs: [shown(files.create!)],
		});
		await shell();
		await open();

		expect(drawn().find(([group]) => group === "This page")).toEqual([
			"This page",
			"Favourite",
			"Copy record URL",
			"Copy record ID",
			"Comment",
			"Attach",
			"Copy link",
		]);
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

		// This tab's visits first, newest first, one row per address, the server's title on its deal.
		expect(drawn()).toEqual([
			["Recent", "CRM Deal CRM", "Acme deal CRM Deal", "CRM Lead CRM", "Call back Acme ToDo"],
			["This page", "Save", "Assign to…", "Send an email", "Go to tab: Activity"],
		]);
	});

	it("draws a visit from this tab before the server has it, by the title its page read", async () => {
		await shell("/crm-deal/DEAL-2");
		recentVisits.retitle("/crm-deal/DEAL-2", "Globex deal");
		await open();

		expect(drawn()[0]).toEqual(["Recent", "Globex deal CRM Deal", "Acme deal CRM Deal", "Call back Acme ToDo"]);
	});

	it("drops the recents the desk once kept in this browser", async () => {
		const kept = [{ href: `${crmBase}/crm-deal/DEAL-1`, label: "Acme deal", kind: "record" }];
		localStorage.setItem("frappe:desk:recents", JSON.stringify({ "reader@example.com": kept }));
		await shell();

		expect(localStorage.getItem("frappe:desk:recents")).toBeNull();
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
			["This page", "Save", "Send an email", "Assign to…"],
			["Desk", "Toggle sidebar"],
			["Go to", "System Settings Desk", "Users Desk", "Deals CRM", "Desk", "ToDo Desk"],
			["Create", "New ToDo Desk"],
		]);

		await type("crm");
		expect(drawn()).toEqual([
			["Desk", "Log a call CRM"],
			[
				"Go to",
				"Deals CRM",
				"CRM",
				"CRM Lead CRM",
				"Probe 0 CRM",
				"Probe 1 CRM",
				"Probe 2 CRM",
				"Probe 3 CRM",
				"Probe 4 CRM",
			],
			["Create", "New CRM Deal CRM", "New Probe 0 CRM", "New Probe 1 CRM", "New Probe 2 CRM", "New Probe 3 CRM"],
		]);
	});

	it("draws the shell's own acts in Desk, those that ask for a value too", async () => {
		await shell("/crm-deal");
		await open();

		await type("sidebar");
		expect(drawn()).toEqual([["Desk", "Customize sidebar"]]);
		await type("log");
		expect(drawn()).toEqual([["Desk", "Log out"]]);
		await type("create");
		expect(drawn()).toEqual([["Desk", "Create"]]);
		await type("theme");
		expect(drawn()).toEqual([["Desk", "Theme"]]);
	});

	it("never draws a denied, hidden or opted-out act", async () => {
		// Off a list or record, so no Find row is pinned and the empty state shows.
		await shell("/");
		await open();

		for (const query of ["delete", "gone", "secret"]) {
			await type(query);
			expect(drawn()).toEqual([]);
		}
		expect(document.body.querySelector("[data-slot='command-palette-empty']")?.textContent).toContain(
			"No results for “secret”"
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

describe("a recent visited under another prefix", () => {
	const href = `${deskBase}/todo/T-9`;

	it("opens under this prefix, as a route of this one", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const router = await shell();
		await open();

		row(`recent:${crmBase}/todo/T-9`)!.click();
		await flush();

		expect(router.currentRoute.value.fullPath).toBe("/todo/T-9");
		expect(assign).not.toHaveBeenCalled();
		assign.mockRestore();
	});

	it("loads its own address from the index, which has no app routes", async () => {
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

	it("goes to a sidebar row in place of its doctype, and New X for a doctype the user may create", async () => {
		await shell("/todo");
		await open();
		await type("deal");

		expect(drawn()).toEqual([
			["Go to", "Deals CRM"],
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

	it("routes to a doctype under this prefix, one another app owns too", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const router = await shell();
		await open();
		await type("lead");
		row("doctype:CRM Lead")!.click();
		await flush();
		expect(router.currentRoute.value.fullPath).toBe("/crm-lead");

		await open();
		await type("todo");
		row("doctype:ToDo")!.click();
		await flush();
		expect(router.currentRoute.value.fullPath).toBe("/todo");
		expect(assign).not.toHaveBeenCalled();
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
		await type("deal", { settle: false });
		expect(row(`sidebar:${crmBase}/crm-deal`)!.dataset.state).toBe("active");
		await press("Tab");
		return router;
	}

	function chip() {
		return document.body.querySelector("[data-slot='palette-chip']");
	}

	function empty() {
		return document.body.querySelector("[data-slot='command-palette-empty']")?.textContent?.trim();
	}

	function footer() {
		return document.body.querySelector("[data-slot='command-palette-footer']")?.textContent ?? "";
	}

	function deal(name: string, label: string) {
		return { doctype: "CRM Deal", name, label, route: `${crmBase}/crm-deal/${name}` };
	}

	it("says Tab searches in the active row's doctype", async () => {
		await shell("/todo");
		await open();
		await type("deal");

		expect(footer()).toContain("to search in CRM Deal");
		await type("system");
		expect(footer()).not.toContain("to search in");
	});

	it("offers no Tab on a single", async () => {
		await shell("/todo");
		await open();

		await type("system");
		expect(footer()).not.toContain("to search in");
		await press("Tab");
		expect(chip()).toBeNull();
	});

	it("narrows on a doctype another app owns", async () => {
		await shell();
		await open();

		await type("todo");
		expect(footer()).toContain("to search in ToDo");
		await press("Tab");
		expect(chip()).not.toBeNull();
	});

	it("leaves Shift+Tab alone", async () => {
		await shell("/todo");
		await open();
		await type("deal");

		input()!.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true }));
		await flush();

		expect(chip()).toBeNull();
	});

	it("says so when the search fails, and searches again on the next pause", async () => {
		server.searchDoctypeRecords
			.mockRejectedValueOnce(new Error("refused"))
			.mockResolvedValueOnce({ data: [deal("DEAL-3", "PivotTech Solutions")] });
		await narrowToDeals();

		await type("pi");
		await vi.waitFor(() => expect(empty()).toBe("Could not search CRM Deal"));
		await type("piv");
		expect(drawn()).toEqual([["Records", "Searching…"]]);
		await vi.waitFor(() => expect(drawn()).toEqual([["Records", "PivotTech Solutions DEAL-3"]]));
	});

	it("asks no cross-doctype record search and pins no Find while narrowed", async () => {
		server.searchDoctypeRecords.mockResolvedValue({ data: [] });
		await narrowToDeals();
		await type("piv");
		await new Promise((resolve) => setTimeout(resolve, 250));

		const asked = searchRecords.mock.calls.map(([, args]) => (args as { txt: string }).txt);
		expect(asked).not.toContain("piv");
		expect(document.body.querySelector("[data-slot='palette-pinned']")).toBeNull();
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
		server.searchDoctypeRecords.mockResolvedValue({ data: [deal("DEAL-3", "PivotTech Solutions")] });
		const router = await narrowToDeals();

		await type("p");
		expect(empty()).toBe("Type to search CRM Deal");
		await type("pi");
		expect(drawn()).toEqual([["Records", "Searching…"]]);
		await type("piv");
		await vi.waitFor(() => expect(drawn()).toEqual([["Records", "PivotTech Solutions DEAL-3"]]));

		expect(server.searchDoctypeRecords).toHaveBeenCalledTimes(1);
		expect(server.searchDoctypeRecords).toHaveBeenCalledWith(
			"frappe.desk.palette.search_doctype_records",
			{ txt: "piv", doctype: "CRM Deal" },
			expect.objectContaining({ http: "GET" })
		);
		// The keyboard was on "Searching…", which cannot be picked; the record takes it.
		await vi.waitFor(() => expect(row("record:CRM Deal/DEAL-3")!.dataset.state).toBe("active"));
		await press("Enter");
		expect(router.currentRoute.value.fullPath).toBe("/crm-deal/DEAL-3");
	});

	it("draws the title with the name alone in gray, and no gray text where the name is the title", async () => {
		server.searchDoctypeRecords.mockResolvedValue({
			data: [deal("DEAL-3", "PivotTech Solutions"), deal("DEAL-4", "DEAL-4")],
		});
		await narrowToDeals();
		await type("deal");

		await vi.waitFor(() => expect(row("record:CRM Deal/DEAL-3")).not.toBeNull());
		expect(description(row("record:CRM Deal/DEAL-3")!)).toBe("DEAL-3");
		expect(description(row("record:CRM Deal/DEAL-4")!)).toBe("");
	});

	it("drops an answer to an older query", async () => {
		let answerFirst: (value: unknown) => void = () => {};
		server.searchDoctypeRecords
			.mockImplementationOnce(() => new Promise((resolve) => (answerFirst = resolve)))
			.mockResolvedValueOnce({ data: [deal("DEAL-5", "Meridian Systems")] });
		await narrowToDeals();

		await type("pi");
		await vi.waitFor(() => expect(server.searchDoctypeRecords).toHaveBeenCalledTimes(1));
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

		// Past Recent's rows, the first of which holds the keyboard.
		const recentRows = drawn()[0].length - 1;
		for (let step = 0; step < recentRows; step++) await press("ArrowDown");
		expect(row("act:header.save")!.dataset.state).toBe("active");
		await press("ArrowDown");
		expect(row("pinned")!.dataset.state).toBe("active");

		await press("Enter");
		expect(ran).toEqual(["pinned"]);
	});

	it("moves the arrow keys in drawn order after the rows change under a pinned row", async () => {
		register({ header: [act("save", "Save"), act("send", "Send")] });
		searchRecords.mockResolvedValue({
			data: ["DEAL-1", "DEAL-2", "DEAL-3"].map((name) => ({ doctype: "CRM Deal", name, label: name })),
		});
		await shell("/crm-deal");
		await open();
		await type("se");

		const drawnIds = Array.from(
			document.body.querySelectorAll<HTMLElement>("[data-slot='command-palette-item']")
		).map((item) => item.dataset.row);
		const activeId = () =>
			document.body.querySelector<HTMLElement>(
				"[data-slot='command-palette-item'][data-state='active']"
			)?.dataset.row;
		const visited = [activeId()];
		for (let step = 1; step < drawnIds.length; step++) {
			await press("ArrowDown");
			visited.push(activeId());
		}
		expect(visited).toEqual(drawnIds);
	});

	it("draws no second list while nothing is pinned", async () => {
		await shell();
		await open();

		expect(document.body.querySelector("[data-slot='palette-pinned']")).toBeNull();
	});
});

describe("records", () => {
	const acme = { doctype: "CRM Deal", name: "DEAL-1", label: "Acme Corp" };

	/** Each record search's arguments, and a way to answer it. */
	function heldSearches() {
		const held: { args: unknown; signal: AbortSignal; answer: (rows: unknown[]) => void }[] = [];
		searchRecords.mockImplementation(
			(_method, args, options) =>
				new Promise((resolve) =>
					held.push({
						args,
						signal: options!.signal!,
						answer: (rows) => resolve({ data: rows }),
					})
				) as never
		);
		return held;
	}

	it("asks the server once the typing pauses, with Searching… meanwhile", async () => {
		const held = heldSearches();
		await shell("/crm-deal/DEAL-9");
		await open();

		await type("ac", { settle: false });
		await type("acm", { settle: false });
		expect(drawn()).toEqual([["Records", "Searching…"]]);
		expect(row("records:searching")!.dataset.disabled).toBe("");
		expect(held).toEqual([]);

		await vi.waitFor(() => expect(held).toHaveLength(1));
		expect(searchRecords).toHaveBeenCalledWith(
			"frappe.desk.palette.search_records",
			{ txt: "acm", doctype: "CRM Deal" },
			expect.objectContaining({ http: "GET" })
		);
		held[0].answer([acme, { doctype: "ToDo", name: "T-1", label: "Call Acme" }]);
		await flush();

		expect(drawn()).toEqual([["Records", "Acme Corp DEAL-1 · CRM Deal", "Call Acme T-1 · ToDo"]]);
	});

	it("drops a question still unanswered when the text changes", async () => {
		const held = heldSearches();
		await shell();
		await open();

		await type("ac", { settle: false });
		await vi.waitFor(() => expect(held).toHaveLength(1));
		await type("acme", { settle: false });
		expect(held[0].signal.aborted).toBe(true);

		await vi.waitFor(() => expect(held).toHaveLength(2));
		held[1].answer([acme]);
		held[0].answer([{ doctype: "ToDo", name: "T-1", label: "Stale" }]);
		await flush();

		expect(drawn()).toEqual([["Records", "Acme Corp DEAL-1 · CRM Deal"]]);
	});

	it("draws the title, then the name and doctype in gray, and no name where it is the title", async () => {
		searchRecords.mockResolvedValue({
			data: [acme, { doctype: "ToDo", name: "Call Acme", label: "Call Acme" }],
		});
		await shell("/");
		await open();
		await type("acme");

		expect(drawn()).toEqual([["Records", "Acme Corp DEAL-1 · CRM Deal", "Call Acme ToDo"]]);
		expect(description(row("record:CRM Deal/DEAL-1")!)).toBe("DEAL-1 · CRM Deal");
		expect(description(row("record:ToDo/Call Acme")!)).toBe("ToDo");
	});

	it("searches nothing under two characters, and no doctype off a list or record", async () => {
		await shell("/");
		await open();

		await type("a", { settle: false });
		await new Promise((resolve) => setTimeout(resolve, 250));
		expect(searchRecords).not.toHaveBeenCalledWith(
			"frappe.desk.palette.search_records",
			expect.anything(),
			expect.anything()
		);

		await type("ac");
		expect(searchRecords).toHaveBeenCalledWith(
			"frappe.desk.palette.search_records",
			{ txt: "ac" },
			expect.anything()
		);
	});

	it("puts the keyboard on the first record once they arrive, when nothing held it", async () => {
		searchRecords.mockResolvedValue({
			data: [acme, { doctype: "ToDo", name: "T-1", label: "Call Acme" }],
		});
		const router = await shell("/");
		await open();
		await type("acme");

		expect(row("record:CRM Deal/DEAL-1")!.dataset.state).toBe("active");
		await press("ArrowDown");
		expect(row("record:ToDo/T-1")!.dataset.state).toBe("active");
		await press("ArrowUp");
		await press("Enter");
		expect(router.currentRoute.value.fullPath).toBe("/crm-deal/DEAL-1");
	});

	it("leaves the keyboard on Find when records arrive above it, and the arrow keys walk them", async () => {
		searchRecords.mockResolvedValue({
			data: [acme, { doctype: "ToDo", name: "T-1", label: "Call Acme" }],
		});
		await shell("/crm-lead");
		await open();
		await type("acme");

		expect(row("find")!.dataset.state).toBe("active");
		await press("ArrowUp");
		expect(row("record:ToDo/T-1")!.dataset.state).toBe("active");
		await press("ArrowUp");
		expect(row("record:CRM Deal/DEAL-1")!.dataset.state).toBe("active");
	});

	it("keeps the keyboard on a row it already holds when records arrive", async () => {
		register({ header: [act("acme_report", "Acme report")] });
		searchRecords.mockResolvedValue({ data: [acme] });
		await shell("/crm-lead");
		await open();
		await type("acme");

		expect(row("act:header.acme_report")!.dataset.state).toBe("active");
	});

	it("says so when the search fails", async () => {
		searchRecords.mockRejectedValue(new Error("server down"));
		await shell();
		await open();
		await type("acme");

		expect(drawn()).toEqual([["Records", "Could not search records"]]);
		expect(row("records:failed")!.dataset.disabled).toBe("");
	});

	it("asks again for the new page's doctype when the page changes while open", async () => {
		const router = await shell("/crm-deal");
		await open();
		await type("acme");
		await router.push("/crm-lead/LEAD-1");
		await flush();
		await vi.waitFor(() => expect(row("records:searching")).toBeNull());

		expect(searchRecords).toHaveBeenLastCalledWith(
			"frappe.desk.palette.search_records",
			{ txt: "acme", doctype: "CRM Lead" },
			expect.anything()
		);
	});

	it("asks nothing once the palette closes during the pause", async () => {
		await shell();
		await open();
		await type("acme", { settle: false });
		paletteOpen.value = false;
		await new Promise((resolve) => setTimeout(resolve, 250));

		expect(searchRecords).not.toHaveBeenCalled();
	});

	it("opens a picked record", async () => {
		searchRecords.mockResolvedValue({ data: [acme] });
		const router = await shell("/crm-lead");
		await open();
		await type("acme");

		row("record:CRM Deal/DEAL-1")!.click();
		await flush();

		expect(router.currentRoute.value.fullPath).toBe("/crm-deal/DEAL-1");
		expect(paletteOpen.value).toBe(false);
	});
});

describe("Find in the current doctype", () => {
	function pinned() {
		return document.body.querySelector("[data-slot='palette-pinned']")?.textContent?.trim();
	}

	it("is pinned on a list or record page once something is typed", async () => {
		await shell("/crm-deal/DEAL-1");
		await open();
		expect(pinned()).toBeUndefined();

		await type("acme");
		expect(pinned()).toBe("Find “acme” in CRM Deal");
	});

	it("is not offered off a list or record page", async () => {
		await shell("/");
		await open();
		await type("acme");

		expect(pinned()).toBeUndefined();
	});

	it("opens the list filtered on the name", async () => {
		const router = await shell("/crm-deal/DEAL-1");
		await open();
		await type("acme");

		row("find")!.click();
		await flush();

		expect(router.currentRoute.value.path).toBe("/crm-deal");
		expect(router.currentRoute.value.query).toEqual({ name: '["LIKE","%acme%"]' });
	});

	it("filters on the title field when the doctype has one", async () => {
		vi.mocked(getMeta).mockResolvedValue({
			data: {
				name: "CRM Deal",
				title_field: "organization",
				fields: [{ fieldname: "organization", fieldtype: "Data", label: "Organization" }],
			},
		} as never);
		await vi.waitFor(() => expect(useDoctypeMeta("CRM Deal").meta.value).not.toBeNull());
		const router = await shell("/crm-deal");
		await open();
		await type("acme");

		row("find")!.click();
		await flush();

		expect(router.currentRoute.value.query).toEqual({ organization: '["LIKE","%acme%"]' });
	});
});

describe("Ask Flow", () => {
	const asked: unknown[] = [];
	const listen = (event: Event) => asked.push((event as CustomEvent).detail);

	beforeEach(() => {
		asked.length = 0;
		window.addEventListener("flow:ask", listen);
	});

	afterEach(() => window.removeEventListener("flow:ask", listen));

	function pinnedArea() {
		return document.body.querySelector("[data-slot='palette-pinned']");
	}

	function pinnedRowIds() {
		return Array.from(pinnedArea()?.querySelectorAll<HTMLElement>("[data-row]") ?? []).map(
			(one) => one.dataset.row
		);
	}

	function empty() {
		return document.body.querySelector("[data-slot='command-palette-empty']")?.textContent?.trim();
	}

	it("never shows while Flow's launcher has not said it is ready", async () => {
		await shell("/");
		await open();
		await type("zzz plan");

		expect(row("ask-flow")).toBeNull();
		expect(empty()).toBe("No results for “zzz plan”");
	});

	it("never shows on the empty query", async () => {
		document.documentElement.dataset.flow = "ready";
		await shell("/");
		await open();

		expect(row("ask-flow")).toBeNull();
		expect(pinnedArea()).toBeNull();
	});

	it("shows alone when nothing else matches, and hands the text to Flow", async () => {
		document.documentElement.dataset.flow = "ready";
		await shell("/");
		await open();
		await type("  zzz plan ");

		expect(drawn()).toEqual([]);
		expect(empty()).toBeUndefined();
		expect(pinnedArea()!.textContent!.replace(/\s+/g, " ").trim()).toBe(
			"Ask Flow: zzz plan New chat in Flow"
		);
		expect(pinnedArea()!.classList).not.toContain("border-t");
		expect(row("ask-flow")!.dataset.state).toBe("active");

		await press("Enter");
		expect(asked).toEqual([{ text: "zzz plan" }]);
		expect(paletteOpen.value).toBe(false);
	});

	it("comes last, after Find, and the arrow keys reach it last", async () => {
		document.documentElement.dataset.flow = "ready";
		register({ header: [act("save", "Save")] });
		await shell();
		await open();
		await type("save");

		expect(drawn()).toEqual([["This page", "Save"]]);
		expect(pinnedRowIds()).toEqual(["find", "ask-flow"]);
		expect(pinnedArea()!.classList).toContain("border-t");
		expect(row("act:header.save")!.dataset.state).toBe("active");
		for (const expected of ["find", "ask-flow", "ask-flow"]) {
			await press("ArrowDown");
			expect(row(expected)!.dataset.state).toBe("active");
		}

		row("ask-flow")!.click();
		await flush();
		expect(asked).toEqual([{ text: "save" }]);
		expect(ran).toEqual([]);
	});

	it("is not pinned while narrowed, so the scope's own prompt shows", async () => {
		document.documentElement.dataset.flow = "ready";
		await shell("/todo");
		await open();
		await type("deal", { settle: false });
		expect(row("ask-flow")).not.toBeNull();
		await press("Tab");

		await type("p");
		expect(row("ask-flow")).toBeNull();
		expect(empty()).toBe("Type to search CRM Deal");
	});
});

describe("the argument step", () => {
	const sarah = { value: "sarah@example.com", label: "Sarah Connor", description: "sarah@example.com" };
	const john = { value: "john@example.com", label: "John Parker", description: "john@example.com" };
	const picked: unknown[] = [];

	/** An "Assign to…" act on the page's header, whose options come from `options`. */
	function assignAct(options: ActArgument["options"], extra: Partial<ActEntry["item"]> = {}) {
		const run = (_page: unknown, value: unknown) => void picked.push(value);
		register({
			header: [act("assign", "Assign to…", { icon: "lucide-user-plus", argument: { label: "Users", options }, run, ...extra })],
		});
	}

	/** An async source whose replies the test sends, in any order. */
	function heldOptions() {
		const held: { query: string; answer: (options: ActOption[]) => void; refuse: () => void }[] = [];
		const options = vi.fn(
			(_context: unknown, query: string) =>
				new Promise<ActOption[]>((resolve, reject) =>
					held.push({ query, answer: resolve, refuse: () => reject(new Error("refused")) })
				)
		);
		return { held, options };
	}

	async function enterAssign() {
		await open();
		await type("assign");
		await press("Enter");
	}

	function chip() {
		return document.body.querySelector("[data-slot='palette-chip']");
	}

	beforeEach(() => {
		picked.length = 0;
	});

	it("keeps the palette open on an act with an argument, with the act as a chip and its options as the list", async () => {
		assignAct(() => [sarah, john]);
		await shell();
		await enterAssign();

		expect(paletteOpen.value).toBe(true);
		expect(chip()?.textContent).toContain("Assign to…");
		expect(input()!.value).toBe("");
		expect(input()!.placeholder).toBe("Search Users");
		expect(drawn()).toEqual([["Users", "Sarah Connor sarah@example.com", "John Parker john@example.com"]]);
		expect(document.body.querySelector("[data-slot='palette-pinned']")).toBeNull();
		expect(picked).toEqual([]);
	});

	it("filters the options as the user types, and Enter runs the act with the picked value", async () => {
		assignAct(() => [sarah, john]);
		await shell();
		await enterAssign();

		await type("jo");
		expect(drawn()).toEqual([["Users", "John Parker john@example.com"]]);
		await press("Enter");

		expect(picked).toEqual(["john@example.com"]);
		expect(paletteOpen.value).toBe(false);
	});

	it("goes back one step on Backspace in an empty input and on the chip's ×", async () => {
		assignAct(() => [sarah]);
		await shell();
		await enterAssign();

		await press("Backspace");
		expect(chip()).toBeNull();
		expect(input()!.placeholder).toBe("Search or run an action");
		expect(paletteOpen.value).toBe(true);

		await type("assign");
		await press("Enter");
		chip()!.querySelector("button")!.click();
		await flush();
		expect(chip()).toBeNull();
		expect(paletteOpen.value).toBe(true);
		expect(picked).toEqual([]);
	});

	it("goes back one step on Esc, and the second Esc closes the palette", async () => {
		assignAct(() => [sarah]);
		await shell();
		await enterAssign();

		await press("Escape");
		expect(chip()).toBeNull();
		expect(paletteOpen.value).toBe(true);
		await press("Escape");
		expect(paletteOpen.value).toBe(false);
	});

	it("asks an async source after a pause, and drops an older reply that lands late", async () => {
		const { held, options } = heldOptions();
		assignAct(options);
		await shell();
		await enterAssign();

		expect(drawn()).toEqual([["Users", "Searching…"]]);
		held[0].answer([sarah, john]);
		await flush();
		expect(drawn()).toEqual([["Users", "Sarah Connor sarah@example.com", "John Parker john@example.com"]]);

		await type("s");
		await type("sa");
		await vi.waitFor(() => expect(held).toHaveLength(2));
		await type("jo");
		await vi.waitFor(() => expect(held).toHaveLength(3));
		held[2].answer([john]);
		await flush();
		held[1].answer([sarah]);
		await flush();

		expect(options.mock.calls.map(([, query]) => query)).toEqual(["", "sa", "jo"]);
		expect(drawn()).toEqual([["Users", "John Parker john@example.com"]]);
	});

	it("shows Searching… while nothing it holds matches the query and the source has not answered", async () => {
		const { held, options } = heldOptions();
		assignAct(options);
		await shell();
		await enterAssign();
		held[0].answer([sarah]);
		await flush();

		await type("emily");
		expect(drawn()).toEqual([["Users", "Searching…"]]);
		await vi.waitFor(() => expect(held).toHaveLength(2));
		held[1].answer([{ value: "emily@example.com", label: "Emily Chen" }]);
		await flush();

		expect(drawn()).toEqual([["Users", "Emily Chen"]]);
		await vi.waitFor(() => expect(row("option:emily@example.com")!.dataset.state).toBe("active"));
	});

	it("says so when the options cannot be read", async () => {
		const { held, options } = heldOptions();
		assignAct(options);
		await shell();
		await enterAssign();
		held[0].refuse();
		await flush();

		expect(drawn()).toEqual([]);
		expect(document.body.querySelector("[data-slot='command-palette-empty']")?.textContent?.trim()).toBe(
			"Could not load Users"
		);
	});

	it("says so when there is nothing to choose from", async () => {
		assignAct(() => []);
		await shell();
		await enterAssign();

		expect(drawn()).toEqual([]);
		expect(document.body.querySelector("[data-slot='command-palette-empty']")?.textContent?.trim()).toBe(
			"Nothing to choose from"
		);
	});

	it("draws an option's avatar, icon and disabled reason, and never picks a disabled one", async () => {
		assignAct(() => [
			{ value: "sarah@example.com", label: "Sarah Connor", image: "/files/sarah.png", disabled: "Assigned" },
			{ value: "john@example.com", label: "John Parker", image: null },
			{ value: "light", label: "Light", icon: "lucide-sun" },
		]);
		await shell();
		await enterAssign();

		const sarahRow = row("option:sarah@example.com")!;
		expect(sarahRow.dataset.disabled).toBe("");
		expect(sarahRow.textContent).toContain("Assigned");
		expect(sarahRow.querySelector("img")?.getAttribute("src")).toBe("/files/sarah.png");
		expect(row("option:john@example.com")!.querySelector(".rounded-full")?.textContent?.trim()).toBe("J");
		expect(row("option:light")!.querySelector(".lucide-sun")).not.toBeNull();

		await type("sarah");
		await press("Enter");
		expect(picked).toEqual([]);
		expect(paletteOpen.value).toBe(true);
	});

	it("draws at most 50 ranked options, and typing finds the rest", async () => {
		const many = Array.from({ length: 80 }, (_, index) => ({
			value: `user${index}@example.com`,
			label: `User ${String(index).padStart(2, "0")}`,
		}));
		assignAct(() => many);
		await shell();
		await enterAssign();

		const [shown] = drawn();
		expect(shown).toHaveLength(51);
		expect(shown.at(-1)).toBe("User 49");

		await type("79");
		expect(drawn()).toEqual([["Users", "User 79"]]);
	});

	it("opens at the act's argument step from its key", async () => {
		assignAct(() => [sarah, john], { key: "Mod+Shift+Y" });
		await shell();
		await import("../actKeys");
		await flush();

		document.body.dispatchEvent(
			new KeyboardEvent("keydown", { key: "y", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })
		);
		await vi.waitFor(() => expect(input()).not.toBeNull(), { timeout: 10000 });
		await flush();

		expect(chip()?.textContent).toContain("Assign to…");
		expect(drawn()).toEqual([["Users", "Sarah Connor sarah@example.com", "John Parker john@example.com"]]);
		expect(picked).toEqual([]);

		await press("Escape");
		expect(chip()).toBeNull();
		expect(paletteOpen.value).toBe(true);
	});

	it("starts afresh on each open, and leaves the step when the page lets go of the act", async () => {
		const options = vi.fn(() => [sarah, john]);
		assignAct(options);
		await shell();
		await enterAssign();
		await type("jo");
		paletteOpen.value = false;
		await flush();

		openArgumentStep("header.assign");
		await flush();
		expect(input()!.value).toBe("");
		expect(drawn()).toEqual([["Users", "Sarah Connor sarah@example.com", "John Parker john@example.com"]]);

		releases.splice(0, 1).forEach((release) => release());
		await flush();
		expect(chip()).toBeNull();
		expect(paletteOpen.value).toBe(true);
	});

	it("matches an option's value as well as its label", async () => {
		assignAct(() => [{ value: "sarah@example.com", label: "Sarah Connor" }, john]);
		await shell();
		await enterAssign();

		await type("sarah@");
		expect(drawn()).toEqual([["Users", "Sarah Connor"]]);
	});

	it("asks nothing more once the palette closes on a pick", async () => {
		const options = vi.fn(() => [sarah, john]);
		assignAct(options);
		await shell();
		await enterAssign();
		await type("jo");
		await vi.waitFor(() => expect(options).toHaveBeenCalledTimes(2));
		await press("Enter");
		await new Promise((resolve) => setTimeout(resolve, 300));

		expect(options).toHaveBeenCalledTimes(2);
		expect(picked).toEqual(["john@example.com"]);
	});

	it("opens at the first step after closing at a step, and Mod+K at a step goes there too", async () => {
		assignAct(() => [sarah, john]);
		await shell();
		await enterAssign();
		paletteOpen.value = false;
		await flush();
		await open();
		expect(chip()).toBeNull();

		await type("assign");
		await press("Enter");
		await type("jo");
		pressModK(input()!);
		await flush();
		expect(chip()).toBeNull();
		expect(input()!.value).toBe("");
	});

	it("opens the settings pane picked at shell.open_settings' step", async () => {
		const router = await shell();
		await open();
		await type("settings");
		expect(row("act:shell.open_settings")!.dataset.state).toBe("active");
		await press("Enter");

		await vi.waitFor(() => expect(drawn()).toEqual([["Settings panes", "Users Desk"]]));
		await press("Enter");
		await flush();

		expect(router.currentRoute.value.hash).toBe("#settings/desk/users");
	});

	it("runs shell.create with the doctype picked from the places", async () => {
		registerCreateDialog({ render: () => null });
		await shell();
		await open();
		await type("create");
		await press("Enter");

		await vi.waitFor(() => expect(drawn()[0]?.[0]).toBe("DocTypes"));
		expect(drawn()[0].slice(1, 3)).toEqual(["CRM Deal CRM", "ToDo Desk"]);
		await type("todo");
		expect(drawn()).toEqual([["DocTypes", "ToDo Desk"]]);
		await press("Enter");
		await flush();

		expect(createRequests.value.map((request) => request.doctype)).toEqual(["ToDo"]);
		closeCreates();
	});
});
