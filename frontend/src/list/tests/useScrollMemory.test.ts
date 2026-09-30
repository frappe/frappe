// A settled list scroll, kept in the session always and in the history entry when it moved.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";

import { forgetRows, readListMemory, recallRows, rememberRows } from "../pageState";
import { useScrollMemory } from "../useScrollMemory";

let scope = effectScope();

beforeEach(() => {
	scope = effectScope();
	vi.useFakeTimers();
	history.replaceState({ position: 3, list: { scrollTop: 240 } }, "");
	rememberRows("Lead", { query: "a", pageSize: 20 });
});

afterEach(() => {
	scope.stop();
	forgetRows("Lead");
	vi.restoreAllMocks();
	vi.useRealTimers();
});

/** The list's viewport, watched, with the history writes from here on counted. */
async function watchedList() {
	const viewport = ref<HTMLElement | null>(null);
	scope.run(() => useScrollMemory(viewport, () => false, { doctype: "Lead", query: () => "a" }));
	const element = document.createElement("div");
	viewport.value = element;
	await nextTick();
	return { element, writes: vi.spyOn(history, "replaceState") };
}

function settleAt(element: HTMLElement, top: number) {
	element.scrollTop = top;
	element.dispatchEvent(new Event("scroll"));
	vi.advanceTimersByTime(150);
}

describe("useScrollMemory", () => {
	it("writes no history entry when a scroll settles at the entry's offset", async () => {
		const { element, writes } = await watchedList();

		settleAt(element, 240);

		expect(writes).not.toHaveBeenCalled();
		expect(recallRows("Lead", "a")?.scrollTop).toBe(240);
	});

	it("writes the history entry when a scroll settles at a new offset", async () => {
		const { element, writes } = await watchedList();

		settleAt(element, 300);

		expect(writes).toHaveBeenCalledOnce();
		expect(readListMemory().scrollTop).toBe(300);
		expect(recallRows("Lead", "a")?.scrollTop).toBe(300);
	});
});
