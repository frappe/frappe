// A pane's drafts against a faked server: each save mode, the per-binding queue, what a save
// sends, the 417 re-send and dialog, a Record's first insert, and the shared cache after a save.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, defineComponent, h, nextTick, onUnmounted } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn() },
}));

import { toast } from "frappe-ui";
import { getDocument } from "@framework/ui/api";
import { clearDataCache, holdDocument, readCachedDocument } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import type { SettingsBlock, SettingsPane } from "@/shell/settingsPanes";
import { PaneDrafts } from "../paneDrafts";
import { SettingsServer, SYSTEM_SETTINGS, TELEPHONY_AGENT, WALK_RULE } from "./settingsServer";

const USER = "reader@example.com";
const SYSTEM = { type: "Single" as const, doctype: "System Settings" };

function block(key: string, save_mode: "auto" | "button", fields: string[], extra: Partial<SettingsBlock> = {}) {
	return { key, app: "frappe", save_mode, binding: SYSTEM, fields, ...extra } as SettingsBlock;
}

function component(key: string, bindings: SettingsBlock["bindings"]) {
	return { key, app: "frappe", save_mode: "auto", component: "probe", bindings } as SettingsBlock;
}

function pane(...blocks: SettingsBlock[]): SettingsPane {
	return { app: "frappe", key: "system", label: "System", blocks };
}

/** A child row as Frappe sends it, stamped by the last save of its parent. */
function rule(value: string, modified: string) {
	return { name: "r1", parentfield: "rules", rule: value, modified, modified_by: "admin@example.com" };
}

let server: SettingsServer;
const confirm = vi.fn();

async function settled() {
	for (let turn = 0; turn < 8; turn++) await new Promise((resolve) => setTimeout(resolve, 0));
	await nextTick();
}

async function opened(...blocks: SettingsBlock[]) {
	const drafts = new PaneDrafts(pane(...blocks), USER, confirm);
	await drafts.loaded;
	return drafts;
}

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	server = new SettingsServer();
	vi.stubGlobal("fetch", server.fetch);
	confirm.mockReset();
	vi.mocked(toast.error).mockClear();
});

afterEach(() => vi.unstubAllGlobals());

describe("a meta that carries no fields", () => {
	it("binds a block to no rows instead of failing the pane", async () => {
		server.metas["System Settings"] = { name: "System Settings", issingle: 1 };
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general");

		expect(general?.draft.state.failed).toBeFalsy();
		expect(general?.fieldnames.value).toEqual([]);
	});
});

describe("save modes", () => {
	it("saves an auto block on commit, sending only its changed fields and modified", async () => {
		const drafts = await opened(
			block("general", "auto", ["country", "enable_onboarding"]),
			block("zone", "button", ["time_zone"])
		);
		const general = drafts.bound.get("general")!;
		const { modified } = server.doc("System Settings", "System Settings");

		general.draft.edit("time_zone", "Asia/Kolkata");
		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(server.writes).toEqual([
			{ method: "PATCH", path: "/api/v2/document/System Settings/System Settings", body: { country: "India", modified } },
		]);
		expect(general.draft.state.marks.country).toBe("saved");
		expect(general.draft.dirty("time_zone")).toBe(true);
		expect(drafts.unsavedCount.value).toBe(1);
	});

	it("saves a button block only from the Save bar", async () => {
		const drafts = await opened(block("zone", "button", ["time_zone"]));
		const zone = drafts.bound.get("zone")!;

		zone.draft.edit("time_zone", "Asia/Kolkata");
		drafts.commit(zone);
		await settled();
		expect(server.writes).toEqual([]);
		expect(drafts.unsavedCount.value).toBe(1);
		expect(drafts.unsaved()).toBe(true);

		await drafts.saveButtons();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ time_zone: "Asia/Kolkata", modified: expect.any(String) },
		]);
		expect(drafts.unsavedCount.value).toBe(0);
		expect(drafts.unsaved()).toBe(false);
	});

	it("keeps an edit made while the Save bar's save is out unsaved, so leaving still asks", async () => {
		const drafts = await opened(block("zone", "button", ["time_zone"]));
		const zone = drafts.bound.get("zone")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		zone.draft.edit("time_zone", "Asia/Kolkata");
		const saving = drafts.saveButtons();
		await settled();
		expect(drafts.unsaved()).toBe(false);
		zone.draft.edit("time_zone", "Asia/Tokyo");
		expect(drafts.unsaved()).toBe(true);

		server.held = null;
		release();
		await saving;
		expect(drafts.unsaved()).toBe(true);
	});

	it("keeps the original value typed back while the Save bar's save is out unsaved", async () => {
		const drafts = await opened(block("zone", "button", ["time_zone"]));
		const zone = drafts.bound.get("zone")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		zone.draft.edit("time_zone", "Asia/Kolkata");
		const saving = drafts.saveButtons();
		await settled();
		zone.draft.edit("time_zone", "Europe/Paris");
		expect(drafts.unsaved()).toBe(true);

		server.held = null;
		release();
		await saving;
		expect(zone.draft.state.doc.time_zone).toBe("Europe/Paris");
		expect(drafts.unsavedCount.value).toBe(1);
	});

	it("puts a button block's changes back on Discard", async () => {
		const drafts = await opened(block("zone", "button", ["time_zone"]));
		const zone = drafts.bound.get("zone")!;
		zone.draft.edit("time_zone", "Asia/Kolkata");

		drafts.discardButtons();

		expect(zone.draft.state.doc.time_zone).toBe("Europe/Paris");
		expect(drafts.unsavedCount.value).toBe(0);
	});
});

describe("the per-binding queue", () => {
	it("sends a change made while a save is in flight in the next save, with the reply's modified", async () => {
		const drafts = await opened(block("general", "auto", ["country", "enable_onboarding"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		general.draft.edit("enable_onboarding", 1);
		drafts.commit(general);
		general.draft.edit("country", "Japan");
		drafts.commit(general);
		await settled();
		expect(server.writes).toHaveLength(1);

		server.held = null;
		release();
		await settled();

		const [first, second] = server.writes;
		expect(first.body).toEqual({ country: "India", modified: expect.any(String) });
		expect(second.body).toEqual({
			country: "Japan",
			enable_onboarding: 1,
			modified: expect.any(String),
		});
		expect(second.body.modified).not.toBe(first.body.modified);
		expect(server.writes).toHaveLength(2);
		expect(general.draft.state.saved).toMatchObject({ country: "Japan", enable_onboarding: 1 });
		expect(general.draft.dirty("country")).toBe(false);
	});

	it("saves a toggle flipped back while its first save was out", async () => {
		const drafts = await opened(block("general", "auto", ["enable_onboarding"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("enable_onboarding", 1);
		drafts.commit(general);
		await settled();
		general.draft.edit("enable_onboarding", 0);
		drafts.commit(general);
		server.held = null;
		release();
		await settled();

		expect(server.writes.map((write) => write.body.enable_onboarding)).toEqual([1, 0]);
		expect(server.doc("System Settings", "System Settings").enable_onboarding).toBe(0);
	});
});

describe("a conflict with a save made elsewhere", () => {
	it("sends the save again with the new modified when the other save touched other fields", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		server.put("System Settings", "System Settings", { time_zone: "Asia/Tokyo" });

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(confirm).not.toHaveBeenCalled();
		expect(server.writes).toHaveLength(2);
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "India",
			time_zone: "Asia/Tokyo",
		});
		expect(general.draft.state.marks.country).toBe("saved");
		expect(general.draft.state.saved.time_zone).toBe("Asia/Tokyo");
	});

	it("sends a table edit again when the other save only restamped the table's rows", async () => {
		server.put("System Settings", "System Settings", { rules: [rule("old", "2026-10-01 10:00:00")] });
		const drafts = await opened(block("rules", "button", ["rules"]));
		const rules = drafts.bound.get("rules")!;
		server.put("System Settings", "System Settings", {
			time_zone: "Asia/Tokyo",
			rules: [rule("old", "2026-10-01 11:00:00")],
		});

		rules.draft.edit("rules", [rule("new", "2026-10-01 10:00:00")]);
		await drafts.saveButtons();
		await settled();

		expect(confirm).not.toHaveBeenCalled();
		expect(server.doc("System Settings", "System Settings").rules).toMatchObject([{ rule: "new" }]);
		expect(rules.draft.dirty("rules")).toBe(false);
	});

	it("saves a table edit kept over a Reload without asking, when the other save left the table alone", async () => {
		server.put("System Settings", "System Settings", { rules: [rule("old", "2026-10-01 10:00:00")] });
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("rules", "button", ["rules"])
		);
		const general = drafts.bound.get("general")!;
		const rules = drafts.bound.get("rules")!;
		rules.draft.edit("rules", [rule("new", "2026-10-01 10:00:00")]);
		server.put("System Settings", "System Settings", {
			country: "Spain",
			rules: [rule("old", "2026-10-01 11:00:00")],
		});
		confirm.mockResolvedValue(true);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		await drafts.saveButtons();
		await settled();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "Spain",
			rules: [{ rule: "new" }],
		});
	});

	it("asks the record page's question when the other save touched a field this save sends", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockResolvedValue(null);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(confirm).toHaveBeenCalledWith(
			expect.objectContaining({
				title: "Saved by someone else",
				message: expect.stringContaining("Ada Admin saved this record after you opened it, so your changes to Country"),
				confirmLabel: "Use their Country",
			})
		);
		expect(server.writes).toHaveLength(1);
		expect(general.draft.state.doc.country).toBe("India");
		expect(general.draft.state.marks.country).toBe("error");
	});

	it("takes the other save's values for the refused fields when the reader chooses Reload", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockResolvedValue(true);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(general.draft.state.doc.country).toBe("Spain");
		expect(general.draft.dirty("country")).toBe(false);
	});

	it("keeps another block's unsaved edits on Reload, and saves them over the reloaded copy", async () => {
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("zone", "button", ["time_zone"])
		);
		const general = drafts.bound.get("general")!;
		const zone = drafts.bound.get("zone")!;
		zone.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockResolvedValue(true);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(general.draft.state.doc.country).toBe("Spain");
		expect(zone.draft.state.doc.time_zone).toBe("Asia/Kolkata");
		expect(zone.draft.dirty("time_zone")).toBe(true);

		const { modified } = server.doc("System Settings", "System Settings");
		await drafts.saveButtons();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(server.writes.at(-1)?.body).toEqual({ time_zone: "Asia/Kolkata", modified });
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "Spain",
			time_zone: "Asia/Kolkata",
		});
	});

	it("still sends an autosave queued behind the refused save after Reload", async () => {
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("onboarding", "auto", ["enable_onboarding"])
		);
		const general = drafts.bound.get("general")!;
		const onboarding = drafts.bound.get("onboarding")!;
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockImplementation(async () => {
			onboarding.draft.edit("enable_onboarding", 0);
			drafts.commit(onboarding);
			return true;
		});

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "Spain",
			enable_onboarding: 0,
		});
		expect(onboarding.draft.state.marks.enable_onboarding).toBe("saved");
	});

	it("names and resets only the fields the other save changed, and saves the rest of the batch", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockResolvedValue(true);

		await drafts.saveButtons();
		await settled();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(confirm.mock.calls[0][0].message).toContain("your changes to Country cannot");
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "Spain",
			time_zone: "Asia/Kolkata",
		});
		expect(regional.draft.dirty("country")).toBe(false);
		expect(regional.draft.dirty("time_zone")).toBe(false);
		expect(regional.draft.state.marks.time_zone).toBe("saved");
	});

	it("sends none of the batch when the reader keeps editing", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain" });
		confirm.mockResolvedValue(null);

		await drafts.saveButtons();
		await settled();

		expect(server.writes).toHaveLength(1);
		expect(server.doc("System Settings", "System Settings").time_zone).toBe("Europe/Paris");
		expect(regional.draft.state.marks).toMatchObject({ country: "error", time_zone: "error" });
		expect(regional.draft.dirty("time_zone")).toBe(true);
	});

	it("does not ask about a kept edit that matches what the other save wrote", async () => {
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("zone", "button", ["time_zone"])
		);
		const general = drafts.bound.get("general")!;
		const zone = drafts.bound.get("zone")!;
		zone.draft.edit("time_zone", "Asia/Tokyo");
		server.put("System Settings", "System Settings", { country: "Spain", time_zone: "Asia/Tokyo" });
		confirm.mockResolvedValue(true);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		zone.draft.edit("time_zone", "Asia/Seoul");
		await drafts.saveButtons();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(server.doc("System Settings", "System Settings").time_zone).toBe("Asia/Seoul");
	});

	it("does not ask when the other save wrote the same value", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		regional.draft.edit("country", "Spain");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain" });

		await drafts.saveButtons();
		await settled();

		expect(confirm).not.toHaveBeenCalled();
		expect(server.doc("System Settings", "System Settings").time_zone).toBe("Asia/Kolkata");
		expect(regional.draft.dirty("country")).toBe(false);
	});

	it("asks again before saving a kept edit the other save also changed", async () => {
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("zone", "button", ["time_zone"])
		);
		const general = drafts.bound.get("general")!;
		const zone = drafts.bound.get("zone")!;
		zone.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain", time_zone: "Asia/Tokyo" });
		confirm.mockResolvedValueOnce(true).mockResolvedValueOnce(null);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		expect(zone.draft.state.doc.time_zone).toBe("Asia/Kolkata");

		await drafts.saveButtons();

		expect(confirm).toHaveBeenCalledTimes(2);
		expect(confirm.mock.calls[1][0].message).toContain("your changes to Time Zone");
		expect(server.doc("System Settings", "System Settings").time_zone).toBe("Asia/Tokyo");
		expect(zone.draft.state.marks.time_zone).toBe("error");
	});

	it("names their changes on the button when the other save changed several fields this save sends", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { country: "Spain", time_zone: "Asia/Tokyo" });
		confirm.mockResolvedValue(null);

		await drafts.saveButtons();
		await settled();

		expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ confirmLabel: "Use their changes" }));
	});

	it("leaves no mark on a field set back while its save was out when the reader keeps editing the other", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		confirm.mockResolvedValue(null);

		const saving = drafts.saveButtons();
		await settled();
		regional.draft.edit("country", "France");
		server.put("System Settings", "System Settings", { country: "Spain", time_zone: "Asia/Tokyo" });
		server.held = null;
		release();
		await saving;
		await settled();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(confirm.mock.calls[0][0].message).toContain("your changes to Time Zone cannot");
		expect(regional.draft.dirty("country")).toBe(false);
		expect(regional.draft.state.marks.country).toBeUndefined();
		expect(regional.draft.state.marks.time_zone).toBe("error");
	});

	it("takes their value for a field set back while its save was out when the reader uses theirs for the other", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");
		confirm.mockResolvedValue(true);

		const saving = drafts.saveButtons();
		await settled();
		regional.draft.edit("country", "France");
		server.put("System Settings", "System Settings", { country: "Spain", time_zone: "Asia/Tokyo" });
		server.held = null;
		release();
		await saving;
		await settled();

		expect(server.writes).toHaveLength(1);
		expect(regional.draft.state.doc).toMatchObject({ country: "Spain", time_zone: "Asia/Tokyo" });
		expect(regional.draft.state.marks).toEqual({});
	});

	it("does not ask about an autosaved field set back while its save was out", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		general.draft.edit("country", "France");
		server.put("System Settings", "System Settings", { country: "Spain" });
		server.held = null;
		release();
		await settled();

		expect(confirm).not.toHaveBeenCalled();
		expect(server.writes).toHaveLength(1);
		expect(general.draft.state.doc.country).toBe("Spain");
		expect(general.draft.dirty("country")).toBe(false);
		expect(general.draft.state.marks.country).toBeUndefined();
	});

	it("saves the rest of a Save bar batch and leaves no mark on a field set back while it was out", async () => {
		const drafts = await opened(block("regional", "button", ["country", "time_zone"]));
		const regional = drafts.bound.get("regional")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));
		regional.draft.edit("country", "India");
		regional.draft.edit("time_zone", "Asia/Kolkata");

		const saving = drafts.saveButtons();
		await settled();
		regional.draft.edit("country", "France");
		server.put("System Settings", "System Settings", { country: "Spain" });
		server.held = null;
		release();
		await saving;
		await settled();

		expect(confirm).not.toHaveBeenCalled();
		expect(server.doc("System Settings", "System Settings")).toMatchObject({
			country: "Spain",
			time_zone: "Asia/Kolkata",
		});
		expect(regional.draft.state.marks.country).toBeUndefined();
		expect(regional.draft.state.marks.time_zone).toBe("saved");
		expect(drafts.unsavedCount.value).toBe(0);
	});
});

describe("a change made elsewhere under an edit not sent yet", () => {
	it("re-sends an autosave silently, then asks before the pending field's own save", async () => {
		const drafts = await opened(
			block("general", "auto", ["country"]),
			block("zone", "button", ["time_zone"])
		);
		const general = drafts.bound.get("general")!;
		const zone = drafts.bound.get("zone")!;
		zone.draft.edit("time_zone", "Asia/Kolkata");
		server.put("System Settings", "System Settings", { time_zone: "Asia/Tokyo" });
		confirm.mockResolvedValue(null);

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		expect(confirm).not.toHaveBeenCalled();
		expect(server.writes).toHaveLength(2);

		await drafts.saveButtons();

		expect(confirm).toHaveBeenCalledTimes(1);
		expect(server.writes).toHaveLength(2);
		expect(server.doc("System Settings", "System Settings").time_zone).toBe("Asia/Tokyo");
		expect(zone.draft.state.marks.time_zone).toBe("error");
	});

	it("refuses a 417 whose re-read shows no newer save, instead of sending again", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		server.refusal = {
			entry: { type: "TimestampMismatchError", message: "Document has been modified" },
			status: 417,
		};

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(server.writes).toHaveLength(1);
		expect(general.draft.state.marks.country).toBe("error");
		expect(confirm).not.toHaveBeenCalled();
	});
});

describe("failures", () => {
	it("keeps a refused value with the server's message, and counts the block on the Save bar", async () => {
		const drafts = await opened(block("zone", "button", ["time_zone"]));
		const zone = drafts.bound.get("zone")!;
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "<b>Mars</b> is not a time zone",
				field_errors: [{ fieldname: "time_zone", message: "Mars is not a time zone" }],
			},
			status: 417,
		};

		zone.draft.edit("time_zone", "Mars");
		await drafts.saveButtons();

		expect(zone.draft.state.doc.time_zone).toBe("Mars");
		expect(zone.draft.fieldErrors.drawn.value.time_zone).toBe("Mars is not a time zone");
		expect(zone.draft.state.marks.time_zone).toBe("error");
		expect(drafts.failedCount.value).toBe(1);
		expect(drafts.unsaved()).toBe(true);

		zone.draft.edit("time_zone", "Europe/Paris");
		expect(zone.draft.state.marks.time_zone).toBeUndefined();
		expect(drafts.failedCount.value).toBe(0);
	});

	it("names the pane in a toast when an autosave fails after the pane closed", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		server.refusal = { entry: { type: "ValidationError", message: "No" }, status: 417 };

		general.draft.edit("country", "India");
		drafts.commit(general);
		drafts.close();
		await settled();

		expect(toast.error).toHaveBeenCalledWith("System did not save");
	});

	it("names no pane when every refused field was set back before the pane closed", async () => {
		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();
		general.draft.edit("country", "France");
		drafts.close();
		server.refusal = { entry: { type: "ValidationError", message: "No" }, status: 417 };
		server.held = null;
		release();
		await settled();

		expect(toast.error).not.toHaveBeenCalled();
	});
});

describe("a Record that does not exist yet", () => {
	const agent = {
		key: "agent",
		app: "crm",
		save_mode: "auto",
		binding: { type: "Record", doctype: "Telephony Agent", resolver: "session_user" },
		fields: ["mobile_no"],
	} as SettingsBlock;

	it("starts from the defaults with its name field filled, inserts on the first save and patches after", async () => {
		const drafts = await opened(agent);
		const bound = drafts.bound.get("agent")!;
		expect(bound.draft.state.isNew).toBe(true);
		expect(bound.draft.state.doc.user).toBe(USER);

		bound.draft.edit("mobile_no", "+91 98");
		drafts.commit(bound);
		await settled();
		bound.draft.edit("mobile_no", "+91 99");
		drafts.commit(bound);
		await settled();

		expect(server.writes.map(({ method, body }) => [method, body])).toEqual([
			["POST", { mobile_no: "+91 98", user: USER }],
			["PATCH", { mobile_no: "+91 99", modified: expect.any(String) }],
		]);
		expect(bound.draft.state.isNew).toBe(false);
	});

	it("skips an autosave while a mandatory field is empty, and marks it", async () => {
		server.metas["Telephony Agent"].fields[2].reqd = 1;
		const drafts = await opened({ ...agent, fields: ["mobile_no", "extension"] });
		const bound = drafts.bound.get("agent")!;

		bound.draft.edit("mobile_no", "+91 98");
		drafts.commit(bound);
		await settled();

		expect(server.writes).toEqual([]);
		expect(bound.draft.fieldErrors.drawn.value.extension).toBe("Extension is required");
		expect(bound.draft.state.marks.mobile_no).toBe("error");
		server.metas["Telephony Agent"].fields[2].reqd = 0;
	});

	it("holds the insert while a button block's mandatory field is empty", async () => {
		server.metas["Telephony Agent"] = {
			...TELEPHONY_AGENT,
			fields: TELEPHONY_AGENT.fields.map((field) =>
				field.fieldname === "extension" ? { ...field, reqd: 1 } : field
			),
		};
		const drafts = await opened(agent, {
			...agent,
			key: "extension",
			save_mode: "button",
			fields: ["extension"],
		});
		const bound = drafts.bound.get("agent")!;

		bound.draft.edit("mobile_no", "+91 98");
		drafts.commit(bound);
		await settled();

		expect(server.writes).toEqual([]);
		expect(bound.draft.fieldErrors.drawn.value.extension).toBe("Extension is required");
		expect(bound.draft.state.marks.mobile_no).toBe("error");
	});

	it("sends a value made required by mandatory_depends_on with the insert", async () => {
		server.metas["Telephony Agent"] = {
			...TELEPHONY_AGENT,
			fields: TELEPHONY_AGENT.fields.map((field) =>
				field.fieldname === "extension" ? { ...field, mandatory_depends_on: "eval:doc.mobile_no" } : field
			),
		};
		const drafts = await opened(agent, { ...agent, key: "extension", save_mode: "button", fields: ["extension"] });
		const bound = drafts.bound.get("agent")!;

		bound.draft.edit("extension", "101");
		bound.draft.edit("mobile_no", "+91 98");
		drafts.commit(bound);
		await settled();

		expect(server.writes.map(({ body }) => body)).toEqual([
			{ mobile_no: "+91 98", extension: "101", user: USER },
		]);
	});

	it("leaves out a value whose mandatory_depends_on is false", async () => {
		server.metas["Telephony Agent"] = {
			...TELEPHONY_AGENT,
			fields: TELEPHONY_AGENT.fields.map((field) =>
				field.fieldname === "extension" ? { ...field, mandatory_depends_on: "eval:!doc.mobile_no" } : field
			),
		};
		const drafts = await opened(agent, { ...agent, key: "extension", save_mode: "button", fields: ["extension"] });
		const bound = drafts.bound.get("agent")!;

		bound.draft.edit("extension", "101");
		bound.draft.edit("mobile_no", "+91 98");
		drafts.commit(bound);
		await settled();

		expect(server.writes.map(({ body }) => body)).toEqual([{ mobile_no: "+91 98", user: USER }]);
	});

	describe("refused on a field no block claims", () => {
		const telephony = {
			...component("telephony", { agent: agent.binding! }),
			fields: ["mobile_no"],
		} as SettingsBlock;
		const phoneNumbers = { fieldname: "phone_nos", fieldtype: "Data", label: "Phone Numbers" };

		beforeEach(() => {
			server.metas["Telephony Agent"] = {
				...TELEPHONY_AGENT,
				fields: [...TELEPHONY_AGENT.fields, phoneNumbers],
			};
			server.refusal = {
				entry: {
					type: "MandatoryError",
					message: "Phone Numbers is required",
					field_errors: [{ fieldname: "phone_nos", message: "Phone Numbers is required" }],
				},
				status: 417,
			};
		});

		it("shows the server's message on the component block that sent the save", async () => {
			const drafts = await opened(telephony);
			const { agent: binding } = drafts.components.get("telephony")!;

			binding.doc.mobile_no = "+91 98";
			await binding.commit();

			expect(server.writes.map(({ method }) => method)).toEqual(["POST"]);
			expect(binding.error).toBe("Phone Numbers is required");
		});

		it("stays off a component block whose fields another block's save left out", async () => {
			const drafts = await opened({ ...agent, fields: ["extension"] }, telephony);
			const extension = drafts.bound.get("agent")!;
			const { agent: binding } = drafts.components.get("telephony")!;

			extension.draft.edit("extension", "101");
			drafts.commit(extension);
			await settled();

			expect(server.writes.map(({ body }) => body)).toEqual([{ extension: "101", user: USER }]);
			expect(extension.draft.fieldErrors.drawn.value.phone_nos).toBe("Phone Numbers is required");
			expect(binding.error).toBe("");
		});

		it("keeps an earlier save's refusal off a component block whose own save names another block's field", async () => {
			const drafts = await opened({ ...agent, fields: ["extension"] }, telephony);
			const extension = drafts.bound.get("agent")!;
			const { agent: binding } = drafts.components.get("telephony")!;

			extension.draft.edit("extension", "101");
			drafts.commit(extension);
			await settled();
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Extension taken",
					field_errors: [{ fieldname: "extension", message: "Extension taken" }],
				},
				status: 417,
			};
			binding.doc.mobile_no = "+91 98";
			await binding.commit();

			expect(server.writes).toHaveLength(2);
			expect(binding.error).toBe("Did not save");
		});

		it("keeps its own save's message when another block's save names the same field", async () => {
			const drafts = await opened({ ...agent, fields: ["extension"] }, telephony);
			const extension = drafts.bound.get("agent")!;
			const { agent: binding } = drafts.components.get("telephony")!;

			binding.doc.mobile_no = "+91 98";
			await binding.commit();
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Phone Numbers are taken",
					field_errors: [{ fieldname: "phone_nos", message: "Phone Numbers are taken" }],
				},
				status: 417,
			};
			extension.draft.edit("extension", "101");
			drafts.commit(extension);
			await settled();

			expect(extension.draft.fieldErrors.drawn.value.phone_nos).toBe("Phone Numbers are taken");
			expect(binding.error).toBe("Phone Numbers is required");
		});
	});

	describe("with a required field filled in another block", () => {
		beforeEach(() => {
			server.metas["Telephony Agent"] = {
				...TELEPHONY_AGENT,
				fields: TELEPHONY_AGENT.fields.map((field) =>
					field.fieldname === "extension" ? { ...field, reqd: 1 } : field
				),
			};
		});

		it("sends a button block's unsaved value with the insert", async () => {
			const drafts = await opened(agent, {
				...agent,
				key: "extension",
				save_mode: "button",
				fields: ["extension"],
			});
			const bound = drafts.bound.get("agent")!;
			const extension = drafts.bound.get("extension")!;

			extension.draft.edit("extension", "101");
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();

			expect(server.writes.map(({ method, body }) => [method, body])).toEqual([
				["POST", { mobile_no: "+91 98", extension: "101", user: USER }],
			]);
			expect(drafts.unsavedCount.value).toBe(0);
			expect(drafts.unsaved()).toBe(false);
		});

		it("sends a component's value with the insert, and only with the insert", async () => {
			const drafts = await opened(agent, {
				...component("extension", { agent: agent.binding! }),
				save_mode: "button",
			});
			const bound = drafts.bound.get("agent")!;
			const { agent: owned } = drafts.components.get("extension")!;

			owned.doc.extension = "101";
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();
			owned.doc.extension = "102";
			bound.draft.edit("mobile_no", "+91 99");
			drafts.commit(bound);
			await settled();

			expect(server.writes.map(({ method, body }) => [method, body])).toEqual([
				["POST", { mobile_no: "+91 98", extension: "101", user: USER }],
				["PATCH", { mobile_no: "+91 99", modified: expect.any(String) }],
			]);
			expect(drafts.unsaved()).toBe(true);
		});

		it("leaves the values it added unmarked when the insert is refused", async () => {
			const drafts = await opened(agent, {
				...agent,
				key: "extension",
				save_mode: "button",
				fields: ["extension"],
			});
			const bound = drafts.bound.get("agent")!;
			server.refusal = { entry: { type: "ValidationError", message: "Server down" }, status: 417 };

			bound.draft.edit("extension", "101");
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();

			expect(bound.draft.state.marks).toEqual({ mobile_no: "error" });
			expect(bound.draft.fieldErrors.drawn.value).toEqual({ mobile_no: "Server down" });
			expect(drafts.failedCount.value).toBe(0);
		});

		it("drops a refusal on a value it added once the insert saves", async () => {
			const drafts = await opened(agent, {
				...component("extension", { agent: agent.binding! }),
				save_mode: "button",
			});
			const bound = drafts.bound.get("agent")!;
			const { agent: owned } = drafts.components.get("extension")!;
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};

			owned.doc.extension = "101";
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();
			expect(owned.error).toBe("Bad extension");

			owned.doc.extension = "102";
			drafts.commit(bound);
			await settled();

			expect(server.writes.at(-1)!.body).toEqual({ mobile_no: "+91 98", extension: "102", user: USER });
			expect(owned.error).toBe("");
		});

		it("marks an added value the refused insert names", async () => {
			const drafts = await opened(agent, {
				...agent,
				key: "extension",
				save_mode: "button",
				fields: ["extension"],
			});
			const bound = drafts.bound.get("agent")!;
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};

			bound.draft.edit("extension", "101");
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();

			expect(bound.draft.state.marks).toEqual({ mobile_no: "error", extension: "error" });
			expect(bound.draft.fieldErrors.drawn.value).toEqual({ extension: "Bad extension" });
			expect(drafts.failedCount.value).toBe(1);
		});

		it("clears the Save bar's refusal on a value a later insert saved", async () => {
			const drafts = await opened(agent, {
				...agent,
				key: "extension",
				save_mode: "button",
				fields: ["extension"],
			});
			const bound = drafts.bound.get("agent")!;
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};

			bound.draft.edit("extension", "101");
			await drafts.saveButtons();
			expect(drafts.failedCount.value).toBe(1);
			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();

			expect(server.writes.at(-1)!.body).toEqual({ mobile_no: "+91 98", extension: "101", user: USER });
			expect(bound.draft.state.marks.extension).toBeUndefined();
			expect(bound.draft.fieldErrors.drawn.value.extension).toBeUndefined();
			expect(drafts.failedCount.value).toBe(0);
		});

		it("keeps a hold placed while a refused insert was out", async () => {
			const drafts = await opened({ ...agent, fields: ["mobile_no", "extension"] });
			const bound = drafts.bound.get("agent")!;
			let release!: () => void;
			server.held = new Promise((resolve) => (release = resolve));

			bound.draft.edit("extension", "101");
			drafts.commit(bound);
			await settled();
			bound.draft.edit("extension", "");
			drafts.commit(bound);
			await settled();
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};
			server.held = null;
			release();
			await settled();

			expect(bound.draft.state.marks.extension).toBe("error");
			expect(bound.draft.fieldErrors.drawn.value.extension).toBe("Extension is required");
		});

		it("keeps a hold through another commit while the insert is out", async () => {
			const drafts = await opened({ ...agent, fields: ["mobile_no", "extension"] });
			const bound = drafts.bound.get("agent")!;
			let release!: () => void;
			server.held = new Promise((resolve) => (release = resolve));

			bound.draft.edit("extension", "101");
			drafts.commit(bound);
			await settled();
			bound.draft.edit("extension", "");
			drafts.commit(bound);
			await settled();
			drafts.commit(bound);
			await settled();
			server.held = null;
			release();
			await settled();

			expect(bound.draft.state.saved.extension).toBe("101");
			expect(bound.draft.state.marks.extension).toBe("error");
			expect(bound.draft.fieldErrors.drawn.value.extension).toBe("Extension is required");
		});

		it("keeps the hold on a field cleared while the insert was out", async () => {
			const drafts = await opened({ ...agent, fields: ["mobile_no", "extension"] });
			const bound = drafts.bound.get("agent")!;
			let release!: () => void;
			server.held = new Promise((resolve) => (release = resolve));

			bound.draft.edit("extension", "101");
			drafts.commit(bound);
			await settled();
			bound.draft.edit("extension", "");
			drafts.commit(bound);
			await settled();
			server.held = null;
			release();
			await settled();

			expect(server.writes.map(({ method }) => method)).toEqual(["POST"]);
			expect(bound.draft.state.marks.extension).toBe("error");
			expect(bound.draft.fieldErrors.drawn.value.extension).toBe("Extension is required");
		});

		describe("cleared in its button block while the insert is out", () => {
			const badExtension = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};

			async function clearedWhileOut() {
				const drafts = await opened(agent, {
					...agent,
					key: "extension",
					save_mode: "button",
					fields: ["extension"],
				});
				const bound = drafts.bound.get("agent")!;
				let release!: () => void;
				server.held = new Promise((resolve) => (release = resolve));
				bound.draft.edit("extension", "101");
				bound.draft.edit("mobile_no", "+91 98");
				drafts.commit(bound);
				await settled();
				bound.draft.edit("extension", "");
				return { drafts, bound, release };
			}

			it("draws no refusal on it when the refused insert names it", async () => {
				const { drafts, bound, release } = await clearedWhileOut();
				server.refusal = badExtension;
				server.held = null;
				release();
				await settled();

				expect(server.writes.map(({ body }) => body)).toEqual([
					{ mobile_no: "+91 98", extension: "101", user: USER },
				]);
				expect(bound.draft.state.marks).toEqual({ mobile_no: "error" });
				expect(bound.draft.fieldErrors.drawn.value).toEqual({});
				expect(drafts.failedCount.value).toBe(0);
			});

			it("keeps the message of a hold placed meanwhile when the refused insert names it", async () => {
				const { drafts, bound, release } = await clearedWhileOut();
				drafts.commit(bound);
				await settled();
				expect(bound.draft.fieldErrors.drawn.value).toEqual({ extension: "Extension is required" });
				server.refusal = badExtension;
				server.held = null;
				release();
				await settled();

				expect(bound.draft.state.marks).toEqual({ mobile_no: "error" });
				expect(bound.draft.fieldErrors.drawn.value).toEqual({ extension: "Extension is required" });
			});

			it("draws the refusal on it once it is typed again after a hold placed meanwhile", async () => {
				const { drafts, bound, release } = await clearedWhileOut();
				drafts.commit(bound);
				await settled();
				bound.draft.edit("extension", "101");
				server.refusal = badExtension;
				server.held = null;
				release();
				await settled();

				expect(bound.draft.state.marks).toEqual({ mobile_no: "error", extension: "error" });
				expect(bound.draft.fieldErrors.drawn.value).toEqual({ extension: "Bad extension" });
				expect(drafts.failedCount.value).toBe(1);
			});

			it("draws a refusal naming the block's own field, which a hold placed meanwhile only marked", async () => {
				const { drafts, bound, release } = await clearedWhileOut();
				drafts.commit(bound);
				await settled();
				server.refusal = {
					entry: {
						type: "ValidationError",
						message: "Bad mobile",
						field_errors: [{ fieldname: "mobile_no", message: "Bad mobile" }],
					},
					status: 417,
				};
				server.held = null;
				release();
				await settled();

				expect(bound.draft.state.marks).toEqual({ mobile_no: "error" });
				expect(bound.draft.fieldErrors.drawn.value).toEqual({
					extension: "Extension is required",
					mobile_no: "Bad mobile",
				});
			});

			it("counts it as sent, not unsaved, until the insert lands", async () => {
				const { drafts, bound, release } = await clearedWhileOut();
				bound.draft.edit("extension", "101");
				expect(drafts.unsaved()).toBe(false);
				server.held = null;
				release();
				await settled();

				expect(bound.draft.state.saved.extension).toBe("101");
				expect(drafts.unsaved()).toBe(false);
			});
		});

		it("drops an older refusal on a component's added value set back while the refused insert was out", async () => {
			const drafts = await opened(agent, {
				...component("extension", { agent: agent.binding! }),
				save_mode: "button",
			});
			const bound = drafts.bound.get("agent")!;
			const { agent: owned } = drafts.components.get("extension")!;
			server.refusal = {
				entry: {
					type: "ValidationError",
					message: "Bad extension",
					field_errors: [{ fieldname: "extension", message: "Bad extension" }],
				},
				status: 417,
			};
			owned.doc.extension = "101";
			await drafts.saveButtons();
			expect(owned.error).toBe("Bad extension");
			server.refusal = { entry: { type: "ValidationError", message: "Server down" }, status: 417 };
			let release!: () => void;
			server.held = new Promise((resolve) => (release = resolve));

			bound.draft.edit("mobile_no", "+91 98");
			drafts.commit(bound);
			await settled();
			owned.doc.extension = "";
			await owned.commit();
			server.held = null;
			release();
			await settled();

			expect(server.writes.at(-1)!.body).toEqual({ mobile_no: "+91 98", extension: "101", user: USER });
			expect(owned.error).toBe("");
			expect(bound.draft.state.marks).toEqual({ mobile_no: "error" });
			expect(drafts.failedCount.value).toBe(0);
		});
	});

	it("draws a new refusal over the older one on a component's field held while the insert is out", async () => {
		server.metas["Telephony Agent"] = {
			...TELEPHONY_AGENT,
			fields: TELEPHONY_AGENT.fields.map((field) =>
				field.fieldname === "mobile_no" ? { ...field, reqd: 1 } : field
			),
		};
		const drafts = await opened(agent, component("extension", { agent: agent.binding! }));
		const bound = drafts.bound.get("agent")!;
		const { agent: owned } = drafts.components.get("extension")!;
		const badExtension = (message: string) => ({
			entry: {
				type: "ValidationError",
				message,
				field_errors: [{ fieldname: "extension", message }],
			},
			status: 417,
		});
		bound.draft.edit("mobile_no", "+91 98");
		server.refusal = badExtension("Bad extension");
		owned.doc.extension = "1";
		await owned.commit();
		expect(owned.error).toBe("Bad extension");
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		owned.doc.extension = "2";
		owned.commit();
		await settled();
		bound.draft.edit("mobile_no", "");
		drafts.commit(bound);
		await settled();
		server.refusal = badExtension("Extension taken");
		server.held = null;
		release();
		await settled();

		expect(server.writes.at(-1)!.body).toEqual({ extension: "2", mobile_no: "+91 98", user: USER });
		expect(bound.draft.state.marks.extension).toBe("error");
		expect(bound.draft.fieldErrors.drawn.value).toEqual({
			mobile_no: "Mobile No is required",
			extension: "Extension taken",
		});
		expect(owned.error).toBe("Extension taken");
	});
});

describe("a required field another block leaves empty", () => {
	beforeEach(() => {
		server.metas["System Settings"] = {
			...SYSTEM_SETTINGS,
			fields: SYSTEM_SETTINGS.fields.map((field) =>
				field.fieldname === "country" ? { ...field, reqd: 1 } : field
			),
		};
	});

	it("keeps the hold on a field cleared while its save was out", async () => {
		const drafts = await opened(block("region", "auto", ["country"]));
		const region = drafts.bound.get("region")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		region.draft.edit("country", "India");
		drafts.commit(region);
		await settled();
		region.draft.edit("country", "");
		drafts.commit(region);
		await settled();
		server.held = null;
		release();
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ country: "India", modified: expect.any(String) },
		]);
		expect(region.draft.state.saved.country).toBe("India");
		expect(region.draft.state.marks.country).toBe("error");
		expect(region.draft.fieldErrors.drawn.value.country).toBe("Country is required");
		expect(drafts.unsaved()).toBe(true);
	});

	it("keeps the hold's message on a field cleared while its save was out, over a refusal naming it", async () => {
		const drafts = await opened(block("region", "auto", ["country"]));
		const region = drafts.bound.get("region")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		region.draft.edit("country", "India");
		drafts.commit(region);
		await settled();
		region.draft.edit("country", "");
		drafts.commit(region);
		await settled();
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "Bad country",
				field_errors: [{ fieldname: "country", message: "Bad country" }],
			},
			status: 417,
		};
		server.held = null;
		release();
		await settled();

		expect(region.draft.state.marks.country).toBe("error");
		expect(region.draft.fieldErrors.drawn.value).toEqual({ country: "Country is required" });
	});

	it("draws a refusal on a field typed again after a hold placed while its save was out", async () => {
		const drafts = await opened(block("region", "auto", ["country"]));
		const region = drafts.bound.get("region")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		region.draft.edit("country", "India");
		drafts.commit(region);
		await settled();
		region.draft.edit("country", "");
		drafts.commit(region);
		await settled();
		region.draft.edit("country", "India");
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "Bad country",
				field_errors: [{ fieldname: "country", message: "Bad country" }],
			},
			status: 417,
		};
		server.held = null;
		release();
		await settled();

		expect(region.draft.state.marks.country).toBe("error");
		expect(region.draft.fieldErrors.drawn.value).toEqual({ country: "Bad country" });
	});

	it("keeps a held table's own message when a refusal names one of its cells", async () => {
		const drafts = await opened(block("general", "auto", ["country", "rules"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("rules", [{ name: "r1", rule: "new" }]);
		drafts.commit(general);
		await settled();
		general.draft.edit("rules", [{ name: "r1", rule: "old" }]);
		general.draft.edit("country", "");
		drafts.commit(general);
		await settled();
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "Bad rule",
				field_errors: [{ parentfield: "rules", row: "r1", fieldname: "rule", message: "Bad rule" }],
			},
			status: 417,
		};
		server.held = null;
		release();
		await settled();

		expect(general.draft.state.marks).toMatchObject({ rules: "error", country: "error" });
		expect(general.draft.fieldErrors.drawn.value).toEqual({ country: "Country is required" });
	});

	it("draws a new refusal over a held table cell's older one", async () => {
		const drafts = await opened(block("general", "auto", ["country", "rules"]));
		const general = drafts.bound.get("general")!;
		const cell = JSON.stringify(["rules", "name:r1", "rule"]);
		const badRule = (message: string) => ({
			entry: {
				type: "ValidationError",
				message,
				field_errors: [{ parentfield: "rules", row: "r1", fieldname: "rule", message }],
			},
			status: 417,
		});
		server.refusal = badRule("Bad rule");
		general.draft.edit("rules", [{ name: "r1", rule: "new" }]);
		drafts.commit(general);
		await settled();
		expect(general.draft.fieldErrors.drawn.value).toEqual({ [cell]: "Bad rule" });
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("rules", [{ name: "r1", rule: "newer" }]);
		drafts.commit(general);
		await settled();
		general.draft.edit("country", "");
		drafts.commit(general);
		await settled();
		server.refusal = badRule("Rule taken");
		server.held = null;
		release();
		await settled();

		expect(general.draft.state.marks).toMatchObject({ rules: "error", country: "error" });
		expect(general.draft.fieldErrors.drawn.value).toEqual({
			country: "Country is required",
			[cell]: "Rule taken",
		});
	});

	it("keeps a refusal with no field off a table whose cell a hold marked meanwhile", async () => {
		server.metas["Walk Rule"] = { ...WALK_RULE, fields: [{ ...WALK_RULE.fields[0], reqd: 1 }] };
		const drafts = await opened(block("general", "auto", ["rules"]));
		const general = drafts.bound.get("general")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		general.draft.edit("rules", [{ name: "r1", rule: "new" }]);
		drafts.commit(general);
		await settled();
		general.draft.edit("rules", [{ name: "r1", rule: "" }]);
		drafts.commit(general);
		await settled();
		server.refusal = { entry: { type: "ValidationError", message: "Server down" }, status: 417 };
		server.held = null;
		release();
		await settled();

		expect(general.draft.state.marks.rules).toBe("error");
		expect(general.draft.fieldErrors.drawn.value).toEqual({
			[JSON.stringify(["rules", "name:r1", "rule"])]: "Rule is required",
		});
	});

	it("does not mark Saved a value typed back while its save was out", async () => {
		const drafts = await opened(block("region", "auto", ["country"]));
		const region = drafts.bound.get("region")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		region.draft.edit("country", "India");
		drafts.commit(region);
		await settled();
		region.draft.edit("country", "");
		drafts.commit(region);
		region.draft.edit("country", "France");
		drafts.commit(region);
		server.held = null;
		release();
		await settled();

		expect(region.draft.state.saved.country).toBe("India");
		expect(region.draft.state.marks.country).toBeUndefined();
		expect(drafts.unsaved()).toBe(true);
	});

	it("autosaves a block while a button block holds the empty field, and still holds that block's Save", async () => {
		const drafts = await opened(
			block("region", "button", ["country", "time_zone"]),
			block("email", "auto", ["enable_onboarding"])
		);
		const region = drafts.bound.get("region")!;
		const email = drafts.bound.get("email")!;

		region.draft.edit("country", "");
		email.draft.edit("enable_onboarding", 1);
		drafts.commit(email);
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ enable_onboarding: 1, modified: expect.any(String) },
		]);
		expect(email.draft.state.marks.enable_onboarding).toBe("saved");

		region.draft.edit("time_zone", "Asia/Kolkata");
		await drafts.saveButtons();

		expect(server.writes).toHaveLength(1);
		expect(region.draft.fieldErrors.drawn.value.country).toBe("Country is required");
		expect(region.draft.state.marks).toMatchObject({ country: "error", time_zone: "error" });
	});

	it("autosaves one block while another auto block on the same record holds its empty field", async () => {
		const drafts = await opened(
			block("name", "auto", ["country"]),
			block("zone", "auto", ["time_zone"])
		);
		const name = drafts.bound.get("name")!;
		const zone = drafts.bound.get("zone")!;

		name.draft.edit("country", "");
		drafts.commit(name);
		await settled();
		expect(server.writes).toEqual([]);

		zone.draft.edit("time_zone", "Asia/Kolkata");
		drafts.commit(zone);
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ time_zone: "Asia/Kolkata", modified: expect.any(String) },
		]);
		expect(zone.draft.state.marks).toMatchObject({ country: "error", time_zone: "saved" });
		expect(name.draft.dirty("country")).toBe(true);
	});

	it("autosaves a component block's field without showing another block's held field as its error", async () => {
		const drafts = await opened(
			block("name", "auto", ["country"]),
			component("zone", { system: SYSTEM })
		);
		const name = drafts.bound.get("name")!;
		const { system } = drafts.components.get("zone")!;

		name.draft.edit("country", "");
		drafts.commit(name);
		await settled();
		system.doc.time_zone = "Asia/Kolkata";
		await system.commit();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ time_zone: "Asia/Kolkata", modified: expect.any(String) },
		]);
		expect(name.draft.fieldErrors.drawn.value.country).toBe("Country is required");
		expect(system.error).toBe("");
	});

	it("shows a component's own refusal, not another block's held field", async () => {
		const drafts = await opened(
			block("name", "auto", ["country"]),
			component("zone", { system: SYSTEM })
		);
		const name = drafts.bound.get("name")!;
		const { system } = drafts.components.get("zone")!;
		name.draft.edit("country", "");
		drafts.commit(name);
		await settled();
		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };

		system.doc.time_zone = "Mars";
		await system.commit();

		expect(system.error).toBe("Not a zone");
	});

	it("saves the Save bar's other block while one button block holds its empty field", async () => {
		const drafts = await opened(
			block("region", "button", ["country", "time_zone"]),
			block("branding", "button", ["app_name"])
		);
		const region = drafts.bound.get("region")!;

		region.draft.edit("country", "");
		region.draft.edit("app_name", "Desk");
		await drafts.saveButtons();
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ app_name: "Desk", modified: expect.any(String) },
		]);
		expect(region.draft.state.marks).toMatchObject({ country: "error", app_name: "saved" });
		expect(drafts.failedCount.value).toBe(1);
	});

	it("holds a block whose table has an empty required cell, and saves another block", async () => {
		server.metas["Walk Rule"] = {
			...WALK_RULE,
			fields: [{ ...WALK_RULE.fields[0], reqd: 1 }],
		};
		const drafts = await opened(
			block("rules", "auto", ["rules"]),
			block("email", "auto", ["enable_onboarding"])
		);
		const rules = drafts.bound.get("rules")!;
		const email = drafts.bound.get("email")!;

		rules.draft.edit("rules", [{ name: "r1", rule: "" }]);
		drafts.commit(rules);
		await settled();
		email.draft.edit("enable_onboarding", 1);
		drafts.commit(email);
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ enable_onboarding: 1, modified: expect.any(String) },
		]);
		expect(Object.values(rules.draft.fieldErrors.drawn.value)).toEqual(["Rule is required"]);
		expect(rules.draft.state.marks.rules).toBe("error");
	});
});

describe("a generated block's refused save", () => {
	it("marks each field it sent with a message that names no field", async () => {
		const drafts = await opened(block("general", "auto", ["country", "enable_onboarding"]));
		const general = drafts.bound.get("general")!;
		server.refusal = { entry: { type: "ValidationError", message: "Server down" }, status: 417 };

		general.draft.edit("country", "India");
		general.draft.edit("enable_onboarding", 1);
		drafts.commit(general);
		await settled();

		expect(general.draft.fieldErrors.drawn.value).toEqual({
			country: "Server down",
			enable_onboarding: "Server down",
		});
	});

	it("is sent again only by its own block's commit", async () => {
		const drafts = await opened(
			block("branding", "auto", ["app_name"]),
			block("zone", "auto", ["time_zone"])
		);
		const branding = drafts.bound.get("branding")!;
		const zone = drafts.bound.get("zone")!;
		server.refusal = { entry: { type: "ValidationError", message: "App name taken" }, status: 417 };

		branding.draft.edit("app_name", "Desk");
		drafts.commit(branding);
		await settled();
		zone.draft.edit("time_zone", "Asia/Kolkata");
		drafts.commit(zone);
		await settled();
		drafts.commit(branding);
		await settled();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ app_name: "Desk", modified: expect.any(String) },
			{ time_zone: "Asia/Kolkata", modified: expect.any(String) },
			{ app_name: "Desk", modified: expect.any(String) },
		]);
	});

	it("leaves a component's error at Did not save when a shared save names only another block's field", async () => {
		const drafts = await opened(
			block("branding", "auto", ["app_name"]),
			component("zone", { system: SYSTEM })
		);
		const branding = drafts.bound.get("branding")!;
		const { system } = drafts.components.get("zone")!;
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "App name taken",
				field_errors: [{ fieldname: "app_name", message: "App name taken" }],
			},
			status: 417,
		};

		branding.draft.edit("app_name", "Desk");
		system.doc.time_zone = "Asia/Kolkata";
		await system.commit();

		expect(server.writes.map((write) => Object.keys(write.body).sort())).toEqual([
			["app_name", "modified", "time_zone"],
		]);
		expect(branding.draft.fieldErrors.drawn.value.app_name).toBe("App name taken");
		expect(system.error).toBe("Did not save");
	});

	it("stays off a component block's error, which shows the component's own refusal", async () => {
		const drafts = await opened(
			block("branding", "button", ["app_name"]),
			component("zone", { system: SYSTEM })
		);
		const branding = drafts.bound.get("branding")!;
		const { system } = drafts.components.get("zone")!;
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "App name taken",
				field_errors: [{ fieldname: "app_name", message: "App name taken" }],
			},
			status: 417,
		};

		branding.draft.edit("app_name", "Desk");
		await drafts.saveButtons();
		system.doc.time_zone = "Asia/Kolkata";
		await system.commit();

		expect(branding.draft.fieldErrors.drawn.value.app_name).toBe("App name taken");
		expect(system.error).toBe("");

		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };
		system.doc.time_zone = "Mars";
		await system.commit();

		expect(system.error).toBe("Not a zone");
	});
});

describe("a component's field set back to its saved value", () => {
	it("loses its refusal on the next commit, so a later save shows no error", async () => {
		const drafts = await opened(component("zone", { system: SYSTEM }));
		const { system } = drafts.components.get("zone")!;
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "Mars is not a time zone",
				field_errors: [{ fieldname: "time_zone", message: "Mars is not a time zone" }],
			},
			status: 417,
		};

		system.doc.time_zone = "Mars";
		await system.commit();
		expect(system.error).toBe("Mars is not a time zone");

		system.doc.time_zone = "Europe/Paris";
		await system.commit();
		expect(system.error).toBe("");
		expect(drafts.unsaved()).toBe(false);

		system.doc.country = "India";
		await system.commit();

		expect(server.writes.map((write) => write.body)).toEqual([
			{ time_zone: "Mars", modified: expect.any(String) },
			{ country: "India", modified: expect.any(String) },
		]);
		expect(system.error).toBe("");
	});

	it("loses a refusal that lands after it was set back", async () => {
		const drafts = await opened(component("zone", { system: SYSTEM }));
		const { system } = drafts.components.get("zone")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		system.doc.time_zone = "Mars";
		const first = system.commit();
		await settled();
		system.doc.time_zone = "Europe/Paris";
		const second = system.commit();
		server.refusal = {
			entry: {
				type: "ValidationError",
				message: "Mars is not a time zone",
				field_errors: [{ fieldname: "time_zone", message: "Mars is not a time zone" }],
			},
			status: 417,
		};
		server.held = null;
		release();
		await Promise.all([first, second]);

		expect(system.error).toBe("");
		system.doc.country = "India";
		await system.commit();
		expect(system.error).toBe("");
	});

	it("loses a button component's refusal on its next commit", async () => {
		const drafts = await opened({ ...component("zone", { system: SYSTEM }), save_mode: "button" });
		const { system } = drafts.components.get("zone")!;
		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };

		system.doc.time_zone = "Mars";
		await drafts.saveButtons();
		expect(system.error).toBe("Not a zone");
		expect(drafts.failedCount.value).toBe(1);

		system.doc.time_zone = "Europe/Paris";
		await system.commit();

		expect(system.error).toBe("");
		expect(drafts.failedCount.value).toBe(0);
	});

	it("loses an older refusal once a later value saves, though it changed again meanwhile", async () => {
		const drafts = await opened(component("zone", { system: SYSTEM }));
		const { system } = drafts.components.get("zone")!;
		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };
		system.doc.time_zone = "Mars";
		await system.commit();
		expect(system.error).toBe("Not a zone");
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		system.doc.time_zone = "Asia/Kolkata";
		const saving = system.commit();
		await settled();
		system.doc.time_zone = "Asia/Tokyo";
		server.held = null;
		release();
		await saving;

		expect(system.error).toBe("");
		expect(drafts.unsaved()).toBe(true);
	});

	it("keeps no refusal for a button component's field set back while the Save bar's save was out", async () => {
		const drafts = await opened({ ...component("zone", { system: SYSTEM }), save_mode: "button" });
		const { system } = drafts.components.get("zone")!;
		let release!: () => void;
		server.held = new Promise((resolve) => (release = resolve));

		system.doc.time_zone = "Mars";
		const saving = drafts.saveButtons();
		await settled();
		system.doc.time_zone = "Europe/Paris";
		await system.commit();
		server.refusal = { entry: { type: "ValidationError", message: "Not a zone" }, status: 417 };
		server.held = null;
		release();
		await saving;

		expect(system.error).toBe("");
		expect(drafts.failedCount.value).toBe(0);
	});
});

describe("the shared data cache", () => {
	/** A component that reads a setting the ruled way: the v2 document read, shown from the cache. */
	const CountryReader = defineComponent({
		setup() {
			onUnmounted(holdDocument("System Settings", "System Settings"));
			void getDocument("System Settings", "System Settings");
			const country = computed(
				() => readCachedDocument("System Settings", "System Settings")?.doc.country
			);
			return () => h("p", String(country.value ?? ""));
		},
	});

	it("updates a component reading System Settings from the cache after the dialog saves it", async () => {
		const host = document.body.appendChild(document.createElement("div"));
		const reader = createApp(CountryReader);
		reader.mount(host);
		await settled();
		expect(host.textContent).toBe("France");

		const drafts = await opened(block("general", "auto", ["country"]));
		const general = drafts.bound.get("general")!;
		general.draft.edit("country", "India");
		drafts.commit(general);
		await settled();

		expect(host.textContent).toBe("India");
		reader.unmount();
	});
});
