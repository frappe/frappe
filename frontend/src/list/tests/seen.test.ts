import { describe, expect, it } from "vitest";
import { cardSeenClass, cellSeenClass, isUnseen, seenColumn } from "../seen";

describe("isUnseen", () => {
	it("is seen when the user is in _seen", () => {
		expect(isUnseen({ _seen: '["a@b.c", "me@x.y"]' }, "me@x.y")).toBe(false);
	});

	it("is unseen when the user is not in _seen", () => {
		expect(isUnseen({ _seen: '["a@b.c"]' }, "me@x.y")).toBe(true);
	});

	it("counts an empty, missing or unreadable _seen as unseen", () => {
		expect(isUnseen({ _seen: "[]" }, "me@x.y")).toBe(true);
		expect(isUnseen({ _seen: "" }, "me@x.y")).toBe(true);
		expect(isUnseen({ _seen: null }, "me@x.y")).toBe(true);
		expect(isUnseen({}, "me@x.y")).toBe(true);
		expect(isUnseen({ _seen: "not json" }, "me@x.y")).toBe(true);
		expect(isUnseen({ _seen: '{"me@x.y": 1}' }, "me@x.y")).toBe(true);
	});

	it("counts every row as unseen for a guest", () => {
		expect(isUnseen({ _seen: '["a@b.c"]' }, null)).toBe(true);
	});
});

describe("seenColumn", () => {
	const meta = { track_seen: 1 as const, title_field: "subject" };

	it("is the title field's column", () => {
		expect(seenColumn(meta, ["status", "subject"])).toBe("subject");
	});

	it("is name when the doctype has no title field", () => {
		expect(seenColumn({ track_seen: 1 }, ["status", "name"])).toBe("name");
	});

	it("is the first column when the list does not show the title", () => {
		expect(seenColumn(meta, ["status", "priority"])).toBe("status");
		expect(seenColumn(meta, [])).toBeNull();
	});

	it("is none when the doctype does not track seen", () => {
		expect(seenColumn({ title_field: "subject" }, ["subject"])).toBeNull();
		expect(seenColumn(null, ["subject"])).toBeNull();
	});
});

describe("the classes", () => {
	it("mark an unseen title in gray-9 medium and a seen one in gray-7", () => {
		expect(cardSeenClass(true)).toBe("font-medium text-ink-gray-9");
		expect(cardSeenClass(false)).toBe("text-ink-gray-7");
		expect(cellSeenClass(true)).toContain("font-medium");
		expect(cellSeenClass(false)).not.toContain("font-medium");
	});
});
