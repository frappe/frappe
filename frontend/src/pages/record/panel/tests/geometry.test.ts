// The panel's width and strip, and what a drag on its edge amounts to.
import { beforeEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import {
	COLLAPSE_AT,
	DEFAULT_WIDTH,
	MAX_WIDTH,
	MIN_WIDTH,
	clampWidth,
	dragOutcome,
	snapToDefault,
	usePanelGeometry,
} from "../geometry";

beforeEach(() => localStorage.clear());

describe("dragOutcome", () => {
	it("resizes within the range and snaps near the default", () => {
		expect(dragOutcome(true, 400, 50)).toEqual({ width: 450 });
		expect(dragOutcome(true, 400, -15)).toEqual({ width: DEFAULT_WIDTH });
		expect(dragOutcome(true, 400, 900)).toEqual({ width: MAX_WIDTH });
	});

	it("collapses past the threshold without committing the squashed width", () => {
		expect(dragOutcome(true, 400, COLLAPSE_AT - 401)).toEqual({ width: 400, toggle: true });
	});

	it("reopens a strip only after a deliberate pull", () => {
		expect(dragOutcome(false, 400, 10)).toEqual({});
		expect(dragOutcome(false, 400, 40)).toEqual({ toggle: true });
	});
});

describe("clampWidth and snapToDefault", () => {
	it("keeps a hand-edited value inside the range", () => {
		expect(clampWidth(10)).toBe(MIN_WIDTH);
		expect(clampWidth(Number.NaN)).toBe(DEFAULT_WIDTH);
		expect(snapToDefault(DEFAULT_WIDTH + 7)).toBe(DEFAULT_WIDTH);
		expect(snapToDefault(DEFAULT_WIDTH + 8)).toBe(DEFAULT_WIDTH + 8);
	});
});

describe("usePanelGeometry", () => {
	it("starts at the default and remembers a width and the strip, per reader", async () => {
		const mine = usePanelGeometry("reader@example.com");
		expect(mine.width.value).toBe(DEFAULT_WIDTH);
		mine.width.value = 500;
		mine.collapsed.value = true;
		await nextTick();

		expect(usePanelGeometry("reader@example.com").width.value).toBe(500);
		expect(usePanelGeometry("reader@example.com").collapsed.value).toBe(true);
		expect(usePanelGeometry("else@example.com").width.value).toBe(DEFAULT_WIDTH);
		expect(usePanelGeometry("else@example.com").collapsed.value).toBe(false);
	});
});
