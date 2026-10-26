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

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
}));

const addresses = new Addresses({
	doctypes: {
		"CRM Deal": ["crm-deal", "fcrm"],
		"CRM Lead": ["crm-lead", "fcrm"],
		ToDo: ["todo", "desk"],
	},
	modules: { fcrm: "FCRM", desk: "Desk" },
});

const deals: NavigationItem = { key: "deals", item_type: "DocType", link_to: "CRM Deal" };

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
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

async function shell(path = "/crm-deal"): Promise<Router> {
	const router = createRouter({
		history: createMemoryHistory(boot.shell_base),
		routes: [
			{ path: "/", name: "home", component: page },
			{ path: "/:doctype", name: "list", component: page },
			{ path: "/:doctype/:name", name: "record", component: page },
		],
	});
	registerShell({ boot, addresses, router });
	recents.track(router, boot, addresses);

	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(AppShell);
	installTranslate(app);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push(path);
	await router.isReady();
	app.mount(host);
	releases.push(() => app.unmount());
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

function pressModK(target: EventTarget = document) {
	const mac = /Mac|iPhone|iPad/i.test(navigator.platform);
	target.dispatchEvent(
		new KeyboardEvent("keydown", { key: "k", ctrlKey: !mac, metaKey: mac, bubbles: true })
	);
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
		await open();

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

		pressModK(editor);
		await flush();

		expect(paletteOpen.value).toBe(false);
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
		register({
			shell: [act("toggle_sidebar", "Toggle sidebar"), act("crm.log_a_call", "Log a call")],
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

	it("ranks a typed query in This page, then Desk with an app act's app", async () => {
		await shell();
		await open();
		await type("s");

		expect(drawn()).toEqual([
			["This page", "Save", "Send an email"],
			["Desk", "Toggle sidebar"],
		]);

		await type("crm");
		expect(drawn()).toEqual([["Desk", "Log a call CRM"]]);
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
