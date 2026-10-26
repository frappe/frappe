// The settings dialog: what an address shows, which groups list, the one refusal, and the held reply.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	runMethod: fake.runMethod,
}));

import type { Boot } from "@/boot";
import { SettingsAddressBook } from "../settingsAddress";
import { fetchPanes, type PanesReply, type SettingsPane } from "../settingsPanes";
import ShellSettingsDialog from "../ShellSettingsDialog.vue";

function pane(app: string, key: string, blocks = ["main"]): SettingsPane {
	return {
		app,
		key,
		label: key[0].toUpperCase() + key.slice(1),
		icon: "settings",
		blocks: blocks.map((block) => ({ key: block, app, save_mode: "auto", label: block })),
	};
}

const REPLY: PanesReply = {
	panes: [
		pane("frappe", "profile", ["details", "notifications"]),
		pane("frappe", "system"),
		pane("crm", "general", ["telephony"]),
		pane("crm", "email-accounts"),
		pane("helpdesk", "tickets"),
	],
	index: [],
	titles: { frappe: "Frappe", crm: "CRM", helpdesk: "Helpdesk" },
};

const PREFIXES = {
	desk: { app: "frappe", modular: false },
	crm: { app: "crm", modular: false },
	helpdesk: { app: "helpdesk", modular: false },
	erp: { app: "erpnext", modular: true },
};

function boot(app: string | null, user = "reader@example.com"): Boot {
	return {
		app,
		prefixes: PREFIXES,
		metadata_version: "v1",
		session: { user: { name: user, full_name: "Reader", email: user } },
	} as unknown as Boot;
}

function book(app: string | null) {
	return new SettingsAddressBook(REPLY, boot(app));
}

describe("the address", () => {
	it("opens the current prefix's first pane for #settings, rewritten to the full address", () => {
		expect(book("crm").resolve([])).toMatchObject({
			prefix: "crm",
			pane: { key: "general" },
			rewrite: ["crm", "general"],
		});
	});

	it("opens desk's first pane on the index and on an app with no panes", () => {
		for (const app of [null, "erpnext"])
			expect(book(app).resolve([])).toMatchObject({ rewrite: ["desk", "profile"] });
	});

	it("opens a prefix's first pane for #settings/<prefix>, and reads a trailing slash as short", () => {
		expect(book("frappe").resolve(["crm"])).toMatchObject({ rewrite: ["crm", "general"] });
		expect(book("frappe").resolve(["crm", ""])).toMatchObject({ rewrite: ["crm", "general"] });
	});

	it("shows a full address as it is", () => {
		const shown = book("frappe").resolve(["desk", "system"]);
		expect(shown).toMatchObject({ prefix: "desk", pane: { key: "system" } });
		expect(shown).not.toHaveProperty("rewrite");
	});

	it("names a known block to scroll to, and drops an unknown one with no message", () => {
		expect(book("frappe").resolve(["desk", "profile", "notifications"])).toMatchObject({
			pane: { key: "profile" },
			block: "notifications",
		});
		const unknown = book("frappe").resolve(["desk", "profile", "nowhere"]);
		expect(unknown).toMatchObject({ pane: { key: "profile" } });
		expect(unknown).not.toHaveProperty("block");
	});

	it("refuses an uninstalled prefix, a pane it lacks or the user cannot see, and a fourth segment", () => {
		const desk = book("frappe");
		expect(desk.resolve(["shop"])).toEqual({ refused: true });
		expect(desk.resolve(["erp"])).toEqual({ refused: true });
		expect(desk.resolve(["desk", "billing"])).toEqual({ refused: true });
		expect(desk.resolve(["desk", "profile", "details", "more"])).toEqual({ refused: true });
	});
});

describe("the groups", () => {
	const listed = (groups: ReturnType<SettingsAddressBook["groups"]>) =>
		groups.map((group) => [group.label, group.panes.map((one) => one.key)]);

	it("lists desk's panes alone, unheaded, when opened from desk", () => {
		expect(listed(book("frappe").groups())).toEqual([[undefined, ["profile", "system"]]]);
	});

	it("adds the current app's group under its title", () => {
		expect(listed(book("crm").groups())).toEqual([
			[undefined, ["profile", "system"]],
			["CRM", ["general", "email-accounts"]],
		]);
	});

	it("adds a visited foreign app's group, and only that one", () => {
		const crm = book("crm");
		expect(crm.isForeign("helpdesk")).toBe(true);
		expect(crm.isForeign("crm")).toBe(false);
		expect(listed(crm.groups("helpdesk")).map(([label]) => label)).toEqual([
			undefined,
			"CRM",
			"Helpdesk",
		]);
	});
});

describe("the pane list", () => {
	beforeEach(() => fake.runMethod.mockReset());

	it("is fetched once per metadata version and user, and a failed read is not kept", async () => {
		fake.runMethod.mockRejectedValueOnce(new Error("offline"));
		await expect(fetchPanes(boot("frappe", "a@example.com"))).rejects.toThrow("offline");

		fake.runMethod.mockResolvedValue({ data: REPLY });
		await fetchPanes(boot("frappe", "a@example.com"));
		await fetchPanes(boot("crm", "a@example.com"));
		await fetchPanes(boot("frappe", "b@example.com"));

		expect(fake.runMethod).toHaveBeenCalledTimes(3);
		expect(fake.runMethod).toHaveBeenCalledWith(
			"frappe.shell.settings.get_panes",
			{},
			{ http: "GET" }
		);
	});
});

describe("the dialog", () => {
	let mounted: App | undefined;
	const flash = vi.fn();
	const scroll = vi.fn();

	beforeEach(() => {
		fake.runMethod.mockReset().mockResolvedValue({ data: REPLY });
		document.body.innerHTML = "";
		Element.prototype.scrollIntoView = scroll;
		Element.prototype.animate = flash;
		flash.mockClear();
		scroll.mockClear();
	});

	afterEach(() => mounted?.unmount());

	async function settle() {
		for (let turn = 0; turn < 4; turn++) {
			await new Promise((resolve) => setTimeout(resolve, 0));
			await nextTick();
		}
	}

	/** Each test is its own user, so the reply held for the tab is never another test's. */
	async function opened(path: string, app = "crm"): Promise<Router> {
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/:any(.*)*", component: { render: () => null } }],
		});
		await router.push(path);
		await router.isReady();
		mounted = createApp(ShellSettingsDialog);
		mounted.provide("boot", boot(app, `${expect.getState().currentTestName}@example.com`));
		mounted.use(router);
		mounted.mount(document.body.appendChild(document.createElement("div")));
		await settle();
		return router;
	}

	const nav = () =>
		Array.from(document.body.querySelectorAll("[role='tab'] .truncate")).map((label) =>
			label.textContent?.trim()
		);
	const content = () => document.body.querySelector("[role='tabpanel'][data-state='active']")?.textContent ?? "";
	const status = () => document.body.querySelector("[role='dialog'] [role='status']:not(.sr-only)");

	it("replaces a short address with the full one, and lists desk then the current app", async () => {
		const router = await opened("/deals#settings");

		expect(router.currentRoute.value.hash).toBe("#settings/crm/general");
		expect(nav()).toEqual(["Profile", "System", "General", "Email-accounts"]);
		expect(content()).toContain("telephony");
	});

	it("shows the one message over the pane list, and keeps the hash, for an address it cannot show", async () => {
		const router = await opened("/deals#settings/desk/billing");

		expect(router.currentRoute.value.hash).toBe("#settings/desk/billing");
		expect(status()?.textContent?.trim()).toBe(
			"This settings pane does not exist, or you cannot see it"
		);
		expect(nav()).toEqual(["Profile", "System", "General", "Email-accounts"]);
		expect(document.body.querySelector("[role='tabpanel'][data-state='active']")).toBeNull();
	});

	it("lists a foreign app's group for the visit, and drops it when the dialog closes", async () => {
		const router = await opened("/deals#settings/helpdesk/tickets");
		expect(nav()).toContain("Tickets");

		await router.replace({ hash: "#settings/desk/system" });
		await settle();
		expect(nav()).toContain("Tickets");

		await router.replace({ hash: "" });
		await settle();
		await router.replace({ hash: "#settings/desk/system" });
		await settle();
		expect(nav()).not.toContain("Tickets");
	});

	it("scrolls to and flashes an addressed block", async () => {
		await opened("/deals#settings/desk/profile/notifications");

		expect(scroll).toHaveBeenCalledTimes(1);
		expect((scroll.mock.contexts[0] as HTMLElement).dataset.block).toBe("notifications");
		expect(flash).toHaveBeenCalledTimes(1);
	});

	it("says the settings could not load, and Try again reads them again", async () => {
		fake.runMethod.mockReset().mockRejectedValueOnce(new Error("offline"));
		await opened("/deals#settings");
		expect(status()?.textContent).toContain("Settings could not load.");
		expect(nav()).toEqual([]);

		fake.runMethod.mockResolvedValue({ data: REPLY });
		Array.from(document.body.querySelectorAll<HTMLElement>("[role='dialog'] button"))
			.find((button) => button.textContent?.trim() === "Try again")!
			.click();
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
		await nextTick();

		expect(status()).toBeNull();
		expect(nav()).toEqual(["Profile", "System", "General", "Email-accounts"]);
	});

	it("replaces the hash for a move inside the dialog", async () => {
		const router = await opened("/deals#settings/crm/general");
		const push = vi.spyOn(router, "push");

		Array.from(document.body.querySelectorAll<HTMLElement>("[role='tab']"))
			.find((tab) => tab.textContent?.trim() === "System")!
			.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
		await settle();

		expect(router.currentRoute.value.hash).toBe("#settings/desk/system");
		expect(push).not.toHaveBeenCalled();
	});
});
