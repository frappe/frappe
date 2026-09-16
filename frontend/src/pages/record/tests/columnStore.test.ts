// One store for every body column: keyed by user, then column name; a patch keeps the
// other key, and a broken or foreign value reads as nothing remembered.
import { beforeEach, describe, expect, it } from "vitest";
import { STORE_KEY, useColumnStore } from "../body/columnStore";

beforeEach(() => localStorage.clear());

describe("useColumnStore", () => {
	it("remembers width and collapsed per user and column, patching one at a time", () => {
		const mine = useColumnStore("reader@example.com");
		expect(mine.remembered("panel")).toBeUndefined();
		mine.remember("panel", { width: 500 });
		mine.remember("panel", { collapsed: true });
		mine.remember("summary", { width: 260 });

		const again = useColumnStore("reader@example.com");
		expect(again.remembered("panel")).toEqual({ width: 500, collapsed: true });
		expect(again.remembered("summary")).toEqual({ width: 260 });
		expect(useColumnStore("else@example.com").remembered("panel")).toBeUndefined();
	});

	it("keeps another user's columns when writing", () => {
		useColumnStore("a@example.com").remember("panel", { width: 400 });
		useColumnStore("b@example.com").remember("panel", { width: 600 });
		const stored = JSON.parse(localStorage.getItem(STORE_KEY)!);
		expect(stored).toEqual({
			"a@example.com": { panel: { width: 400 } },
			"b@example.com": { panel: { width: 600 } },
		});
	});

	it("reads a value it cannot parse as nothing", () => {
		localStorage.setItem(STORE_KEY, "{not json");
		expect(useColumnStore("reader@example.com").remembered("panel")).toBeUndefined();
		localStorage.setItem(STORE_KEY, JSON.stringify({ "reader@example.com": 7 }));
		expect(useColumnStore("reader@example.com").remembered("panel")).toBeUndefined();
	});
});
