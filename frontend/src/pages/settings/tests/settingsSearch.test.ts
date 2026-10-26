// Settings search in the dialog with its registered blocks: results in place of the pane list, the
// keys, and a pick that opens the pane, shows the field's tab, and scrolls to and flashes the field.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import type { Boot } from "@/boot";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { registerSettingsBlocks } from "@/shell/settingsBlocks";
import type { PanesReply } from "@/shell/settingsPanes";
import ShellSettingsDialog from "@/shell/ShellSettingsDialog.vue";
import SettingsBlocks from "../SettingsBlocks.vue";
import { SettingsServer } from "./settingsServer";

const WALK_SETTINGS = {
	name: "Walk Settings",
	issingle: 1,
	fields: [
		{ fieldname: "general_tab", fieldtype: "Tab Break", label: "General" },
		{ fieldname: "greeting", fieldtype: "Data", label: "Greeting" },
		{ fieldname: "dates_tab", fieldtype: "Tab Break", label: "Dates" },
		{ fieldname: "time_zone", fieldtype: "Data", label: "Time Zone" },
	],
};

const WALK = { type: "Single", doctype: "Walk Settings" } as const;

const REPLY: PanesReply = {
	panes: [
		{ app: "frappe", key: "profile", label: "Profile", icon: "user", blocks: [] },
		{
			app: "frappe",
			key: "walk",
			label: "Walk",
			icon: "settings",
			blocks: [{ key: "main", app: "frappe", save_mode: "auto", label: "Walking", binding: WALK }],
		},
		{ app: "crm", key: "general", label: "General", icon: "settings", blocks: [] },
	],
	index: [
		{ app: "frappe", pane: "walk", block: "main", fieldname: "greeting", label: "Greeting" },
		{ app: "frappe", pane: "walk", block: "main", fieldname: "time_zone", label: "Time Zone" },
		{ app: "crm", pane: "general", block: "main", label: "Zone Routing" },
	],
	titles: { frappe: "Frappe", crm: "CRM" },
};

let mounted: App | undefined;
const scroll = vi.fn();
const flash = vi.fn();

registerSettingsBlocks(async () => ({ default: SettingsBlocks }));

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	const server = new SettingsServer();
	server.metas["Walk Settings"] = WALK_SETTINGS;
	server.put("Walk Settings", "Walk Settings", { greeting: "Hi", time_zone: "Asia/Kolkata" });
	const handle = server.fetch.getMockImplementation()!;
	server.fetch.mockImplementation(async (url, init) =>
		String(url).includes("frappe.shell.settings.get_panes")
			? new Response(JSON.stringify({ data: REPLY }))
			: handle(url, init)
	);
	vi.stubGlobal("fetch", server.fetch);
	Element.prototype.scrollIntoView = scroll;
	Element.prototype.animate = flash;
	scroll.mockClear();
	flash.mockClear();
	document.body.innerHTML = "";
});

afterEach(() => {
	mounted?.unmount();
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 10; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function opened(hash: string): Promise<Router> {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:any(.*)*", component: { render: () => null } }],
	});
	await router.push("/home");
	await router.push({ path: "/home", hash });
	await router.isReady();
	mounted = createApp(ShellSettingsDialog);
	mounted.provide("boot", {
		app: null,
		prefixes: { desk: { app: "frappe", modular: false }, crm: { app: "crm", modular: false } },
		metadata_version: "v1",
		session: { user: { name: `${expect.getState().currentTestName}@example.com` } },
	} as unknown as Boot);
	mounted.use(router);
	mounted.mount(document.body.appendChild(document.createElement("div")));
	await settle();
	return router;
}

const box = () =>
	document.body.querySelector<HTMLInputElement>("input[aria-label='Search settings']")!;
const results = () =>
	Array.from(document.body.querySelectorAll("[data-slot='item-list-row']")).map((row) =>
		Array.from(row.querySelectorAll("[data-slot='item-label'] > span"), (line) => line.textContent).join(" | ")
	);
const navItems = () =>
	Array.from(document.body.querySelectorAll("[role='tab']")).filter(
		(tab) => !tab.closest("[style*='display: none']")
	);

async function search(query: string) {
	box().value = query;
	box().dispatchEvent(new Event("input", { bubbles: true }));
	await nextTick();
}

async function press(key: string) {
	box().dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
	await settle();
}

describe("settings search", () => {
	it("replaces the pane list with this app's results, then other apps' under their heading", async () => {
		await opened("#settings/desk/profile");
		expect(navItems().length).toBe(2);

		await search("zone");

		expect(navItems()).toEqual([]);
		expect(results()).toEqual(["Time Zone | Walk › Walking", "Zone Routing | CRM › General"]);
		expect(document.body.querySelector("[data-results='other']")?.textContent).toContain(
			"In other apps"
		);

		await search("nothing like it");
		expect(document.body.textContent).toContain("No settings match “nothing like it”");
	});

	it("opens a picked field's pane, shows its tab, and scrolls to and flashes the field", async () => {
		const router = await opened("#settings/desk/profile");
		await search("time");
		await press("Enter");

		expect(router.currentRoute.value.hash).toBe("#settings/desk/walk");
		const row = document.body.querySelector<HTMLElement>("[data-fieldname='time_zone']");
		expect(row).not.toBeNull();
		expect(document.body.querySelector("[data-fieldname='greeting']")).toBeNull();
		expect(scroll.mock.contexts).toEqual([row]);
		expect(flash.mock.contexts).toEqual([row!.querySelector(":scope > [data-flash]")]);
	});

	it("moves through the results with the arrow keys", async () => {
		const router = await opened("#settings/desk/walk");
		await search("zone");
		await press("ArrowDown");
		expect(document.body.querySelector("[data-state='active'][data-slot='item-list-row']")?.textContent).toContain(
			"Zone Routing"
		);
		await press("ArrowDown");
		await press("Enter");

		expect(router.currentRoute.value.hash).toBe("#settings/desk/walk");
		expect(flash).toHaveBeenCalledTimes(1);
	});

	it("scrolls to a block address in the same pane after a pick", async () => {
		const router = await opened("#settings/desk/walk");
		await search("time");
		await press("Enter");
		scroll.mockClear();

		await router.replace({ hash: "#settings/desk/walk/main" });
		await settle();

		expect(scroll.mock.contexts).toEqual([document.body.querySelector("[data-block='main']")]);
	});

	it("flashes a picked pane's title", async () => {
		await opened("#settings/desk/profile");
		await search("walk");
		await press("Enter");

		const title = Array.from(document.body.querySelectorAll("h2")).find(
			(heading) => heading.textContent === "Walk"
		)!;
		expect(flash.mock.contexts).toEqual([title.parentElement!.querySelector(":scope > [data-flash]")]);
	});

	it("clears the query when the dialog closes", async () => {
		const router = await opened("#settings/desk/profile");
		await search("zone");
		await router.replace({ hash: "" });
		await settle();
		await router.replace({ hash: "#settings/desk/profile" });
		await settle();

		expect(box().value).toBe("");
		expect(navItems().length).toBe(2);
	});
});
