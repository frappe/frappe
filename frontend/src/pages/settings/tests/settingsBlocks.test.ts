// The settings dialog with its registered blocks: rows drawn from the binding, the save mark,
// the Save bar and Ctrl/Cmd+S, the missing Record's note, and the question before leaving.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const fake = vi.hoisted(() => ({ confirm: vi.fn() }));
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	dialog: { confirm: fake.confirm },
	toast: { success: vi.fn(), error: vi.fn() },
}));

import type { Boot } from "@/boot";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { registerSettingsBlocks, type PanesReply, type SettingsBlock } from "@/shell/settingsPanes";
import ShellSettingsDialog from "@/shell/ShellSettingsDialog.vue";
import SettingsBlocks from "../SettingsBlocks.vue";
import { SettingsServer } from "./settingsServer";

const SYSTEM = { type: "Single", doctype: "System Settings" } as const;

const BLOCKS: SettingsBlock[] = [
	{
		key: "general",
		app: "frappe",
		save_mode: "auto",
		label: "General",
		binding: SYSTEM,
		fields: ["country", "enable_onboarding", "app_name"],
		read_only_fields: ["app_name"],
	},
	{ key: "zone", app: "frappe", save_mode: "button", label: "Zone", binding: SYSTEM, fields: ["time_zone"] },
	{
		key: "agent",
		app: "frappe",
		save_mode: "auto",
		label: "Calls",
		binding: { type: "Record", doctype: "Telephony Agent", resolver: "session_user" },
		fields: ["mobile_no"],
	},
];

const REPLY: PanesReply = {
	panes: [
		{ app: "frappe", key: "system", label: "System", icon: "settings", blocks: BLOCKS },
		{ app: "frappe", key: "profile", label: "Profile", icon: "user", blocks: [] },
	],
	index: [],
	titles: { frappe: "Frappe" },
};

let server: SettingsServer;
let mounted: App | undefined;

registerSettingsBlocks(async () => ({ default: SettingsBlocks }));

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	server = new SettingsServer();
	const handle = server.fetch.getMockImplementation()!;
	server.fetch.mockImplementation(async (url, init) =>
		String(url).includes("frappe.shell.settings.get_panes")
			? new Response(JSON.stringify({ data: REPLY }))
			: handle(url, init)
	);
	vi.stubGlobal("fetch", server.fetch);
	fake.confirm.mockReset();
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

async function opened(): Promise<Router> {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:any(.*)*", component: { render: () => null } }],
	});
	await router.push("/deals#settings/desk/system");
	await router.isReady();
	mounted = createApp(ShellSettingsDialog);
	mounted.provide("boot", {
		app: null,
		prefixes: { desk: { app: "frappe", modular: false } },
		metadata_version: "v1",
		session: { user: { name: `${expect.getState().currentTestName}@example.com` } },
	} as unknown as Boot);
	mounted.use(router);
	mounted.mount(document.body.appendChild(document.createElement("div")));
	await settle();
	return router;
}

const row = (fieldname: string) =>
	document.body.querySelector<HTMLElement>(`[data-fieldname="${fieldname}"]`)!;
const input = (fieldname: string) => row(fieldname).querySelector("input")!;
const bar = () => document.body.querySelector<HTMLElement>("[role='status'].absolute");

function type(fieldname: string, value: string) {
	input(fieldname).value = value;
	input(fieldname).dispatchEvent(new Event("input", { bubbles: true }));
}

describe("a generated block", () => {
	it("reads each binding once, and draws a row per field, a Check as a switch and a read-only field disabled", async () => {
		await opened();

		expect(row("country").textContent).toContain("Country");
		expect(input("country").value).toBe("France");
		expect(row("enable_onboarding").querySelector("[role='switch']")).not.toBeNull();
		expect(input("app_name").disabled).toBe(true);
		expect(input("country").disabled).toBe(false);
		const reads = server.fetch.mock.calls.filter(([url]) =>
			String(url).includes("/document/System%20Settings/")
		);
		expect(reads).toHaveLength(1);
	});

	it("tells the reader a Record does not exist yet", async () => {
		await opened();

		expect(document.body.querySelector("[data-block='agent']")!.textContent).toContain(
			"No Telephony Agent for you yet. The first change creates it."
		);
	});

	it("saves an auto block when a typed field commits, and marks the row", async () => {
		await opened();

		type("country", "India");
		await settle();
		expect(server.writes).toEqual([]);

		input("country").dispatchEvent(new Event("change", { bubbles: true }));
		await settle();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ country: "India", modified: expect.any(String) },
		]);
		expect(row("country").textContent).toContain("Saved");
	});
});

describe("the Save bar", () => {
	it("counts a button block's changes and saves them on Save", async () => {
		await opened();

		type("time_zone", "Asia/Kolkata");
		input("time_zone").dispatchEvent(new Event("change", { bubbles: true }));
		await settle();
		expect(server.writes).toEqual([]);
		expect(bar()?.textContent).toContain("1 unsaved change");

		Array.from(bar()!.querySelectorAll("button"))
			.find((button) => button.textContent?.trim() === "Save")!
			.click();
		await settle();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ time_zone: "Asia/Kolkata", modified: expect.any(String) },
		]);
		expect(bar()).toBeNull();
	});

	it("saves on Ctrl+S and says how many blocks did not save", async () => {
		await opened();
		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };

		type("time_zone", "Mars");
		input("time_zone").dispatchEvent(
			new KeyboardEvent("keydown", { key: "s", ctrlKey: true, bubbles: true })
		);
		await settle();

		expect(server.writes).toHaveLength(1);
		expect(bar()?.textContent).toContain("1 block did not save");
		expect(row("time_zone").textContent).toContain("Not saved");
		expect(row("time_zone").textContent).toContain("Not a zone");
	});
});

describe("leaving with unsaved changes", () => {
	it("asks before a pane switch, and stays when the reader keeps editing", async () => {
		const router = await opened();
		type("time_zone", "Asia/Kolkata");
		fake.confirm.mockImplementation((options) => options.onCancel());

		await router.replace({ hash: "#settings/desk/profile" });
		await settle();

		expect(fake.confirm).toHaveBeenCalledWith(
			expect.objectContaining({ title: "Discard unsaved changes?" })
		);
		expect(router.currentRoute.value.hash).toBe("#settings/desk/system");
	});

	it("asks before a click on another pane in the list, and keeps this pane drawn", async () => {
		const router = await opened();
		type("time_zone", "Asia/Kolkata");
		fake.confirm.mockImplementation((options) => options.onCancel());

		Array.from(document.body.querySelectorAll<HTMLElement>("[role='tab']"))
			.find((tab) => tab.textContent?.trim() === "Profile")!
			.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
		await settle();

		expect(fake.confirm).toHaveBeenCalledTimes(1);
		expect(router.currentRoute.value.hash).toBe("#settings/desk/system");
		expect(input("time_zone").value).toBe("Asia/Kolkata");
	});

	it("leaves without asking when nothing is unsaved", async () => {
		const router = await opened();

		await router.replace({ hash: "" });
		await settle();

		expect(fake.confirm).not.toHaveBeenCalled();
		expect(router.currentRoute.value.hash).toBe("");
	});
});
