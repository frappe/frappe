import { describe, expect, it } from "vitest";
import { placeCaret, textOffsetAt } from "../openAtClick";

function area(value: string, scrollHeight: number, clientHeight = 128) {
	const el = document.createElement("textarea");
	el.value = value;
	Object.defineProperty(el, "scrollHeight", { value: scrollHeight });
	Object.defineProperty(el, "clientHeight", { value: clientHeight });
	return el;
}

describe("placeCaret", () => {
	it("puts the caret at the click and shows the top, whatever the focus scrolled to", () => {
		const el = area("one\ntwo\nthree", 300);
		el.scrollTop = 280;
		placeCaret(el, 5);
		expect([el.selectionStart, el.selectionEnd, el.scrollTop]).toEqual([5, 5, 0]);
	});

	it("opens a text that fits with the caret at the end", () => {
		const el = area("one\ntwo", 48);
		placeCaret(el, null);
		expect(el.selectionStart).toBe(el.value.length);
	});

	it("opens a text taller than the box with the caret at the start, on the top", () => {
		const el = area("one\ntwo\nthree", 300);
		el.scrollTop = 280;
		placeCaret(el, null);
		expect([el.selectionStart, el.scrollTop]).toEqual([0, 0]);
	});
});

describe("textOffsetAt", () => {
	it("is null when the browser cannot name a text position", () => {
		expect(textOffsetAt(document.createElement("span"), 1, 1)).toBeNull();
	});
});
