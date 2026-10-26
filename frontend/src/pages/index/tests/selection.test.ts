// The index's one arrow-key movement: across a grid, and on into the next section.
import { describe, expect, it } from "vitest";
import { Selection, type SelectionSection } from "../selection";

function items(prefix: string, count: number) {
	return Array.from({ length: count }, (_, index) => ({
		key: `${prefix}${index}`,
		href: `/${prefix}${index}`,
	}));
}

/** Eight tiles in six columns, then a three-row list. */
const PAGE: SelectionSection[] = [
	{ items: items("tile", 8), columns: 6 },
	{ items: items("row", 3), columns: 1 },
];

function walk(keys: string[], sections = PAGE) {
	const selection = new Selection(() => sections);
	for (const key of keys) selection.move(key);
	return selection.selected.value;
}

describe("the index selection", () => {
	it("starts on the first item with any arrow", () => {
		for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"])
			expect(walk([key])).toBe("tile0");
	});

	it("moves along a row and wraps into the next row", () => {
		expect(walk(["ArrowRight", "ArrowRight"])).toBe("tile1");
		expect(walk(["ArrowRight", ...Array(6).fill("ArrowRight")])).toBe("tile6");
	});

	it("moves down a column, onto the last tile when the row below is short", () => {
		expect(walk(["ArrowRight", "ArrowDown"])).toBe("tile6");
		const toFourth = ["ArrowRight", "ArrowRight", "ArrowRight", "ArrowRight"];
		expect(walk([...toFourth, "ArrowDown"])).toBe("tile7");
	});

	it("goes on from the grid's last row into the next section, and back up", () => {
		expect(walk(["ArrowRight", "ArrowDown", "ArrowDown"])).toBe("row0");
		expect(walk(["ArrowRight", "ArrowDown", "ArrowDown", "ArrowDown"])).toBe("row1");
		expect(walk(["ArrowRight", "ArrowDown", "ArrowDown", "ArrowUp"])).toBe("tile7");
	});

	it("stays put at either end of the page", () => {
		expect(walk(["ArrowRight", "ArrowLeft"])).toBe("tile0");
		expect(walk(["ArrowRight", "ArrowUp"])).toBe("tile0");
		expect(walk(["ArrowRight", ...Array(20).fill("ArrowDown")])).toBe("row2");
	});

	it("skips a section with no items", () => {
		const sections = [PAGE[0], { items: [], columns: 1 }, PAGE[1]];
		expect(walk(["ArrowRight", "ArrowDown", "ArrowDown"], sections)).toBe("row0");
	});

	it("answers false for a key that is not an arrow", () => {
		expect(new Selection(() => PAGE).move("Enter")).toBe(false);
	});

	it("targets the selected item, else the first, for Enter", () => {
		const selection = new Selection(() => PAGE);
		expect(selection.target()?.key).toBe("tile0");
		selection.selected.value = "row1";
		expect(selection.target()?.key).toBe("row1");
		selection.selected.value = "gone";
		expect(selection.target()?.key).toBe("tile0");
	});

	it("has no target on an empty page", () => {
		const selection = new Selection(() => []);
		expect(selection.move("ArrowDown")).toBe(true);
		expect(selection.selected.value).toBeNull();
		expect(selection.target()).toBeUndefined();
	});
});
