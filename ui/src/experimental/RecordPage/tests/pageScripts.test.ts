// The Page Script tier (wayfinder ticket 15) as executable claims.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { call, toast, evaluatePageScript } = vi.hoisted(() => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	// Blob-URL modules are the real mechanism, but node cannot import one; the
	// evaluator's own contract is the browser verification's job.
	evaluatePageScript: vi.fn(),
}));

vi.mock("frappe-ui", () => ({ call, toast }));
vi.mock("../evaluatePageScript", () => ({ evaluatePageScript }));

import { loadPageScripts, reloadPageScripts, resetPageScripts } from "../pageScripts";
import { registrationsFor, resetRegistry } from "../registry";

function respond(scripts: string[], canWrite = true) {
	call.mockResolvedValue({
		scripts: scripts.map((name) => ({ name, script: "export default {}" })),
		can_write: canWrite,
	});
}

function sources(doctype = "CRM Deal") {
	return registrationsFor(doctype).map((registration) => registration.source);
}

describe("the Page Script tier", () => {
	beforeEach(() => {
		resetRegistry();
		resetPageScripts();
		call.mockReset();
		toast.error.mockReset();
		evaluatePageScript.mockReset();
		evaluatePageScript.mockImplementation(async () => ({ refresh: () => {} }));
		vi.spyOn(console, "error").mockImplementation(() => {});
	});

	it("registers the doctype's scripts as sources, in the order served", async () => {
		respond(["oldest", "newest"]);
		await loadPageScripts("CRM Deal");
		expect(sources()).toEqual(["page-script:oldest", "page-script:newest"]);
	});

	it("fetches once per doctype", async () => {
		respond(["only"]);
		await loadPageScripts("CRM Deal");
		await loadPageScripts("CRM Deal");
		expect(call).toHaveBeenCalledTimes(1);
	});

	it("skips a script that fails to load, keeping the rest of the tier", async () => {
		respond(["broken", "fine"]);
		evaluatePageScript.mockImplementation(async (row: { name: string }) => {
			if (row.name === "broken") throw new SyntaxError("Unexpected token");
			return { refresh: () => {} };
		});
		await loadPageScripts("CRM Deal");
		expect(sources()).toEqual(["page-script:fine"]);
	});

	it("toasts a failure once per script, only for script editors", async () => {
		respond(["broken"], false);
		evaluatePageScript.mockRejectedValue(new SyntaxError("Unexpected token"));
		await loadPageScripts("CRM Deal");
		expect(toast.error).not.toHaveBeenCalled();

		respond(["broken"], true);
		await reloadPageScripts("CRM Deal");
		await reloadPageScripts("CRM Deal");
		expect(toast.error).toHaveBeenCalledTimes(1);
	});

	it("re-registers the whole tier on reload, so creation order survives a save", async () => {
		respond(["oldest", "newest"]);
		await loadPageScripts("CRM Deal");
		await reloadPageScripts("CRM Deal");
		expect(sources()).toEqual(["page-script:oldest", "page-script:newest"]);
	});

	it("drops a deleted script's source on reload", async () => {
		respond(["kept", "deleted"]);
		await loadPageScripts("CRM Deal");
		respond(["kept"]);
		await reloadPageScripts("CRM Deal");
		expect(sources()).toEqual(["page-script:kept"]);
	});

	it("leaves the page scriptless when the fetch fails", async () => {
		call.mockRejectedValue(new Error("offline"));
		await loadPageScripts("CRM Deal");
		expect(sources()).toEqual([]);
	});
});
