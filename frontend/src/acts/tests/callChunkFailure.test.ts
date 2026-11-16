import { describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));
vi.mock("../callResult", () => {
	throw new Error("Failed to fetch dynamically imported module");
});

import { ActDispatcher, type ActScope } from "../dispatcher";

function held(run: () => unknown) {
	const dispatcher = new ActDispatcher();
	dispatcher.register({
		surfaces: { header: () => [{ item: { name: "go", run }, hidden: false }] },
		context: () => null,
		passes: () => true,
		settled: () => undefined,
		hold: async (work: () => unknown) => work(),
		failed: () => {},
	} as unknown as ActScope);
	return dispatcher;
}

describe("call when the result's wording cannot load", () => {
	it("keeps the outcome of an act that finished", async () => {
		expect(await held(() => 7).call("header.go")).toMatchObject({ ok: true, data: 7, dialogs: [] });
	});

	it("reports an act that threw as failed, without rejecting", async () => {
		const result = await held(() => Promise.reject(new Error("Server said no"))).call("header.go");

		expect(result).toMatchObject({ ok: false, error: { code: "failed", message: expect.stringContaining("Server said no") } });
	});
});
