import { describe, expect, it, vi } from "vitest";

const runMethod = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { fetchContents } from "@/contents";

describe("fetchContents", () => {
	it("reads the contents as a GET through the wrapper", async () => {
		const entries = [{ doctype: "Note", slug: "note", module: "desk" }];
		runMethod.mockResolvedValueOnce({ data: entries });

		await expect(fetchContents("frappe", "desk")).resolves.toEqual(entries);
		expect(runMethod).toHaveBeenCalledWith(
			"frappe.shell.doctypes.get_contents",
			{ app: "frappe", module: "desk" },
			{ http: "GET" }
		);
	});

	it("sends no module when none is asked for", async () => {
		runMethod.mockResolvedValueOnce({ data: [] });

		await expect(fetchContents("frappe")).resolves.toEqual([]);
		expect(runMethod).toHaveBeenLastCalledWith(
			"frappe.shell.doctypes.get_contents",
			{ app: "frappe" },
			{ http: "GET" }
		);
	});

	it("rejects when the wrapper throws", async () => {
		runMethod.mockRejectedValueOnce(new Error("no such app"));

		await expect(fetchContents("nope")).rejects.toThrow("no such app");
	});
});
