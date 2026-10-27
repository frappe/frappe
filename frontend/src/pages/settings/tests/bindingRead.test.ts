// A binding's first read: a Record the server does not have is new and logs nothing, while every
// other refusal, and a Single's 404, still fails the draft.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import type { SettingsBinding, SettingsBlock } from "@/shell/settingsPanes";
import { PaneDrafts } from "../paneDrafts";
import { SettingsServer } from "./settingsServer";

const USER = "reader@example.com";
const AGENT: SettingsBinding = {
	type: "Record",
	doctype: "Telephony Agent",
	resolver: "session_user",
};
const SYSTEM: SettingsBinding = { type: "Single", doctype: "System Settings" };

let server: SettingsServer;
let logged: ReturnType<typeof vi.spyOn>[];

beforeEach(() => {
	resetDoctypeMeta();
	clearDataCache();
	server = new SettingsServer();
	vi.stubGlobal("fetch", server.fetch);
	logged = [vi.spyOn(console, "error"), vi.spyOn(console, "warn")];
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe("reading a binding", () => {
	it("makes a Record the server answers 404 for new, and logs nothing", async () => {
		const draft = await opened(AGENT);

		const read = expect.stringContaining("/document/Telephony%20Agent/reader%40example.com");
		expect(server.fetch).toHaveBeenCalledWith(read, expect.anything());
		expect(draft.state.isNew).toBe(true);
		expect(draft.state.failed).toBe("");
		for (const spy of logged) expect(spy).not.toHaveBeenCalled();
	});

	it.each([403, 500])("fails a Record read answered %i", async (status) => {
		refuseDocumentReads(status);
		const draft = await opened(AGENT);

		expect(draft.state.failed).toBe(`Refused with ${status}`);
		expect(draft.state.doc).toEqual({});
	});

	it("fails a Single the server answers 404 for", async () => {
		server.docs.delete("System Settings/System Settings");
		const draft = await opened(SYSTEM);

		expect(draft.state.failed).toContain("not found");
		expect(draft.state.doc).toEqual({});
	});
});

async function opened(binding: SettingsBinding) {
	const block = { key: "probe", app: "frappe", save_mode: "auto", binding, fields: [] };
	const pane = { app: "frappe", key: "probe", label: "Probe", blocks: [block as SettingsBlock] };
	const drafts = new PaneDrafts(pane, USER, vi.fn());
	await drafts.loaded;
	return drafts.bound.get("probe")!.draft;
}

function refuseDocumentReads(status: number) {
	const answer = server.fetch.getMockImplementation()!;
	server.fetch.mockImplementation(async (url, init) => {
		const path = decodeURIComponent(new URL(String(url), "http://x").pathname);
		if (!path.startsWith("/api/v2/document/")) return answer(url, init);
		const type = status === 403 ? "PermissionError" : "InternalServerError";
		const errors = [{ type, message: `Refused with ${status}` }];
		return new Response(JSON.stringify({ errors }), { status });
	});
}
