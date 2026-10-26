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
import { SettingsServer } from "./settingsServer";

const USER = "reader@example.com";
const SYSTEM = { type: "Single" as const, doctype: "System Settings" };

function block(key: string, save_mode: "auto" | "button", fields: string[], extra: Partial<SettingsBlock> = {}) {
	return { key, app: "frappe", save_mode, binding: SYSTEM, fields, ...extra } as SettingsBlock;
}

function pane(...blocks: SettingsBlock[]): SettingsPane {
	return { app: "frappe", key: "system", label: "System", blocks };
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
				confirmLabel: "Reload and lose my changes",
			})
		);
		expect(server.writes).toHaveLength(1);
		expect(general.draft.state.doc.country).toBe("India");
		expect(general.draft.state.marks.country).toBe("error");
	});

	it("reloads the binding when the reader chooses Reload", async () => {
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
