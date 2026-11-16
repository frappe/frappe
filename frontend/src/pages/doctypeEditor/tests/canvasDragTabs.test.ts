// Holding a field or section on another tab's name opens that tab; nothing selects while a drag is in flight.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { holdOnTab, releaseFromTab, dropSection } from "../canvasDrops";
import { openTabsOnDwell, TAB_DWELL_MS } from "../tabDwell";
import { acts } from "@/acts/dispatcher";
import { mountEditor, taskNote } from "./editorFixture";


const section = (name: string) => ({ name, sections: [{ name: `${name}_s`, columns: [{ name: `${name}_c`, fields: ["subject"] }] }] });
let stop: (() => void) | undefined;
function canvas() {
	const state = taskNote();
	state.layouts.Details![0].layout = [section("a"), section("b")] as never;
	const editor = mountEditor(state);
	stop = editor.stop;
	vi.spyOn(acts, "perform").mockResolvedValue(undefined as never);
	return editor.canvas;
}
afterEach(() => {
	stop?.();
	vi.useRealTimers();
});

describe("a held field or section", () => {
	it("reopens the tab it came from when no drop landed", () => {
		const c = canvas();
		holdOnTab(c);
		c.openTabName.value = "b";
		releaseFromTab(c);
		expect(c.openTabName.value).toBe("a");
		expect(c.held.value).toBeNull();
	});

	it("leaves the new tab open once a drop landed", () => {
		const c = canvas();
		holdOnTab(c);
		c.openTabName.value = "b";
		dropSection(c, { moved: { element: c.tabs.value[1].sections[0], newIndex: 0 } }, "b");
		releaseFromTab(c);
		expect(c.openTabName.value).toBe("b");
	});
});

describe("the tab dwell", () => {
	beforeEach(() => vi.useFakeTimers());

	function pointerOn(name: string | null) {
		const tab = document.createElement("div");
		if (name) tab.dataset.canvasTab = name;
		document.elementFromPoint = () => tab;
		window.dispatchEvent(new Event("pointermove"));
	}

	it("opens a tab after the dwell, not on a pass across the strip", () => {
		const c = canvas();
		const end = openTabsOnDwell(c);
		pointerOn("b");
		vi.advanceTimersByTime(TAB_DWELL_MS - 100);
		pointerOn("a");
		vi.advanceTimersByTime(TAB_DWELL_MS);
		expect(c.openTabName.value).not.toBe("b");
		pointerOn("b");
		vi.advanceTimersByTime(TAB_DWELL_MS);
		expect(c.openTabName.value).toBe("b");
		end();
	});
});

describe("text selection", () => {
	it("is off for the whole page while a drag's ghost is on it", () => {
		const css = readFileSync(`${__dirname}/../EditorCanvas.vue`, "utf8");
		expect(css).toMatch(/body:has\(\.sortable-fallback\)\s*\{\s*@apply select-none;/);
	});
});

describe("a tab the held field left", () => {
	// display:none would hide the ghost Sortable keeps inside the list, and happy-dom draws no layout.
	it("collapses without display:none and keeps the ghost visible", () => {
		const form = readFileSync(`${__dirname}/../CanvasForm.vue`, "utf8");
		const css = readFileSync(`${__dirname}/../EditorCanvas.vue`, "utf8");
		expect(form).not.toMatch(/v-show="drawn/);
		expect(form).toContain("canvas-tab-held");
		expect(css).toMatch(/\.canvas-tab-held \.sortable-fallback\s*\{\s*visibility: visible;/);
	});
});
