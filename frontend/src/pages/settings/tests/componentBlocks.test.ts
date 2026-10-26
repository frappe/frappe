// A component block's named bindings against a faked server: `commit()` in each save mode, the
// draft it shares with a generated block, a block with no binding, and the after-save registry.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn() },
}));

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { registerAfterSave } from "@/shell/afterSave";
import type { SettingsBlock, SettingsPane } from "@/shell/settingsPanes";
import { PaneDrafts } from "../paneDrafts";
import { SettingsServer } from "./settingsServer";

const USER = "reader@example.com";
const SYSTEM = { type: "Single" as const, doctype: "System Settings" };
const AGENT = {
	type: "Record" as const,
	doctype: "Telephony Agent",
	resolver: "session_user" as const,
};

function component(
	key: string,
	save_mode: "auto" | "button",
	bindings: SettingsBlock["bindings"]
) {
	return {
		key,
		app: "frappe",
		save_mode,
		component: "probe",
		bindings,
	} as SettingsBlock;
}

let server: SettingsServer;

async function settled() {
	for (let turn = 0; turn < 8; turn++) await new Promise((resolve) => setTimeout(resolve, 0));
	await nextTick();
}

async function opened(...blocks: SettingsBlock[]) {
	const pane: SettingsPane = {
		app: "frappe",
		key: "system",
		label: "System",
		blocks,
	};
	const drafts = new PaneDrafts(pane, USER, vi.fn());
	await drafts.loaded;
	return drafts;
}

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	server = new SettingsServer();
	vi.stubGlobal("fetch", server.fetch);
});

afterEach(() => vi.unstubAllGlobals());

describe("a component block's bindings", () => {
	it("gives each named binding its draft, saved copy, meta and state", async () => {
		const drafts = await opened(component("calls", "auto", { system: SYSTEM, agent: AGENT }));
		const { system, agent } = drafts.components.get("calls")!;

		expect(system.doc.country).toBe("France");
		expect(system.saved.country).toBe("France");
		expect(system.meta?.name).toBe("System Settings");
		expect(system.loading).toBe(false);
		expect(system.error).toBe("");
		expect(system.isNew).toBe(false);
		expect(agent.isNew).toBe(true);
		expect(agent.doc.user).toBe(USER);
	});

	it("saves only the changed fields plus modified on commit() in auto mode, and reads the reply live", async () => {
		const drafts = await opened(component("calls", "auto", { system: SYSTEM }));
		const { system } = drafts.components.get("calls")!;
		const { modified } = server.doc("System Settings", "System Settings");

		system.doc.country = "India";
		await system.commit();

		expect(server.writes.map((write) => write.body)).toEqual([{ country: "India", modified }]);
		expect(system.saved.country).toBe("India");
		expect(system.saved.modified).toBe(
			server.doc("System Settings", "System Settings").modified
		);
		expect(drafts.unsaved()).toBe(false);
	});

	it("keeps the doc a component held across a save live", async () => {
		const drafts = await opened(component("calls", "auto", { system: SYSTEM }));
		const { system } = drafts.components.get("calls")!;
		const doc = system.doc;

		doc.country = "India";
		await system.commit();
		doc.country = "Japan";
		await system.commit();

		expect(server.writes.map((write) => write.body.country)).toEqual(["India", "Japan"]);
		expect(system.doc).toBe(doc);
		expect(system.saved.country).toBe("Japan");
	});

	it("sends nothing on commit() in button mode; the Save bar saves the change", async () => {
		const drafts = await opened(component("calls", "button", { system: SYSTEM }));
		const { system } = drafts.components.get("calls")!;

		system.doc.app_name = "Acme";
		await system.commit();
		await settled();
		expect(server.writes).toEqual([]);
		expect(drafts.hasButtons).toBe(true);
		expect(drafts.unsavedCount.value).toBe(1);
		expect(drafts.unsaved()).toBe(true);

		await drafts.saveButtons();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ app_name: "Acme", modified: expect.any(String) },
		]);
		expect(drafts.unsaved()).toBe(false);
	});

	it("shares the draft with a generated block, and leaves that block's fields to its own save", async () => {
		const drafts = await opened(
			{
				key: "zone",
				app: "frappe",
				save_mode: "button",
				binding: SYSTEM,
				fields: ["time_zone"],
			},
			component("calls", "auto", { system: SYSTEM })
		);
		const zone = drafts.bound.get("zone")!;
		const { system } = drafts.components.get("calls")!;

		zone.draft.edit("time_zone", "Asia/Kolkata");
		expect(system.doc.time_zone).toBe("Asia/Kolkata");
		system.doc.country = "India";
		await system.commit();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ country: "India", modified: expect.any(String) },
		]);
		expect(drafts.unsavedCount.value).toBe(1);
	});
});

describe("a component block with no binding", () => {
	it("reads nothing and stays out of the pane's dirty state and Save bar", async () => {
		const drafts = await opened(component("theme", "auto", undefined));

		expect(drafts.components.has("theme")).toBe(false);
		expect(drafts.hasButtons).toBe(false);
		expect(drafts.unsaved()).toBe(false);
		expect(server.fetch).not.toHaveBeenCalled();
	});
});

describe("the after-save registry", () => {
	it("runs a doctype's handlers with the saved record and the fields sent", async () => {
		const ran = vi.fn();
		const unregister = registerAfterSave("System Settings", ran);
		try {
			const drafts = await opened(component("calls", "auto", { system: SYSTEM }));
			const { system } = drafts.components.get("calls")!;
			system.doc.time_zone = "Asia/Kolkata";
			await system.commit();
		} finally {
			unregister();
		}

		expect(ran).toHaveBeenCalledTimes(1);
		expect(ran).toHaveBeenCalledWith({
			doctype: "System Settings",
			name: "System Settings",
			doc: expect.objectContaining({ time_zone: "Asia/Kolkata" }),
			changed: ["time_zone"],
		});
	});

	it("does not run after a refused save", async () => {
		const ran = vi.fn();
		const unregister = registerAfterSave("System Settings", ran);
		try {
			const drafts = await opened(component("calls", "auto", { system: SYSTEM }));
			const { system } = drafts.components.get("calls")!;
			server.refusal = {
				entry: { type: "ValidationError", message: "Not a zone" },
				status: 417,
			};
			system.doc.time_zone = "Mars";
			await system.commit();
			expect(system.error).toContain("Not a zone");
		} finally {
			unregister();
		}

		expect(ran).not.toHaveBeenCalled();
	});
});
