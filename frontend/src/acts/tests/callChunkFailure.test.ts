import { describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));
vi.mock("../callResult", () => {
	throw new Error("Failed to fetch dynamically imported module");
});

import { ActDispatcher, type ActScope } from "../dispatcher";

describe("call when the result's wording cannot load", () => {
	it("still resolves, saying it failed", async () => {
		const dispatcher = new ActDispatcher();
		const scope = {
			surfaces: { header: () => [{ item: { name: "go", run: () => 1 }, hidden: false }] },
			context: () => null,
			passes: () => true,
			settled: () => undefined,
			hold: async (work: () => unknown) => work(),
			failed: () => {},
		} as unknown as ActScope;
		dispatcher.register(scope);

		expect(await dispatcher.call("header.go")).toMatchObject({
			ok: false,
			error: { code: "failed", message: expect.stringContaining("Error") },
			route: expect.any(String),
			dialogs: [],
		});
	});
});
