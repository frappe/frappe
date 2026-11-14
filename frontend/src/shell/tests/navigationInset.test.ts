// The inset the corner floats add to their right offset, and the toast viewport's rule for it.
import { readFileSync } from "node:fs";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import { describe, expect, it, vi } from "vitest";
import {
	keepClearOfNavigation,
	navigationOvershoot,
	navigationShift,
	navInsetBottom,
	navInsetLeft,
	navInsetRight,
	useNavigationInset,
} from "../navigationInset";
import { navigationSide } from "../navigationSide";
import { clampPlacement, MARGIN } from "../windowDrag";

// The content's measured box, which only changes when the content itself resizes.
const bounds = vi.hoisted(() => ({ width: { value: 0 } }));
vi.mock("@vueuse/core", async (original) => {
	const { ref } = await import("vue");
	bounds.width = ref(1000);
	return { ...(await original<object>()), useElementBounding: () => ({ width: bounds.width, left: ref(0) }) };
});

describe("useNavigationInset", () => {
	it("follows a side change that moves the content without resizing it", async () => {
		// A 1280px window and 1000px of content: the navigation's 280px is on whichever side it is drawn.
		const clientWidth = vi.spyOn(document.documentElement, "clientWidth", "get").mockReturnValue(1280);
		navigationSide.value = "start";
		const app = createApp(
			defineComponent({
				setup() {
					useNavigationInset(ref(document.createElement("div")));
					return () => h("div");
				},
			})
		);
		app.mount(document.createElement("div"));
		await nextTick();
		expect([navInsetLeft.value, navInsetRight.value]).toEqual([280, 0]);

		navigationSide.value = "end";
		await nextTick();
		expect([navInsetLeft.value, navInsetRight.value]).toEqual([0, 280]);

		app.unmount();
		clientWidth.mockRestore();
		navigationSide.value = "start";
	});
});

describe("the toast viewport", () => {
	it("adds the navigation's inset to sonner's right offset", () => {
		const css = readFileSync("src/index.css", "utf8");
		expect(css).toMatch(
			/\[data-sonner-toaster\]\[data-x-position="right"\]\s*\{\s*right: calc\(var\(--offset-right\) \+ var\(--shell-nav-inset-right, 0px\)\);/
		);
	});
});

describe("the bottom inset", () => {
	it("lifts a toast above the tab bar", () => {
		const css = readFileSync("src/index.css", "utf8");
		expect(css).toContain("var(--offset-bottom, 32px) + var(--shell-nav-inset-bottom, 0px)");
		expect(css).toContain("var(--mobile-offset-bottom, 16px) + var(--shell-nav-inset-bottom, 0px)");
	});

	it("keeps a dragged standing window above the tab bar", () => {
		const viewport = { width: 390, height: 800 };
		expect(clampPlacement({ left: 0, bottom: 0 }, viewport, 300).bottom).toBe(MARGIN);

		navInsetBottom.value = 59;
		expect(clampPlacement({ left: 0, bottom: 0 }, viewport, 300).bottom).toBe(MARGIN + 59);
		navInsetBottom.value = 0;
	});
});

describe("keepClearOfNavigation", () => {
	function card(top: number, height: number) {
		const element = document.createElement("div");
		element.style.left = "10px";
		element.style.top = `${top}px`;
		Object.defineProperty(element, "offsetWidth", { value: 300 });
		Object.defineProperty(element, "offsetHeight", { value: height });
		return element;
	}

	it("lifts a card that reaches into the tab bar", () => {
		const root = document.documentElement;
		Object.defineProperty(root, "clientWidth", { value: 390, configurable: true });
		Object.defineProperty(root, "clientHeight", { value: 800, configurable: true });
		navInsetBottom.value = 59;
		const low = card(500, 300);
		const stop = keepClearOfNavigation(low);
		expect(low.style.transform).toBe("translateY(-59px)");
		stop();
		expect(low.style.transform).toBe("");

		const clear = card(100, 300);
		keepClearOfNavigation(clear)();
		expect(clear.style.transform).toBe("");
		navInsetBottom.value = 0;
	});
});

describe("navigationOvershoot", () => {
	it("is how far the float's right end reaches into the navigation", () => {
		expect(navigationOvershoot(940, 460, 1400, 320)).toBe(320);
		expect(navigationOvershoot(800, 460, 1400, 320)).toBe(180);
	});

	it("is nothing for a float clear of the navigation, or with no navigation on the right", () => {
		expect(navigationOvershoot(600, 460, 1400, 320)).toBe(0);
		expect(navigationOvershoot(940, 460, 1400, 0)).toBe(0);
	});

	it("never pulls the float's left end past the window's left edge", () => {
		// A float wider than the room beside the navigation stays at the left edge.
		expect(navigationOvershoot(200, 900, 1000, 320)).toBe(200);
		for (const left of [0, 100, 500, 940]) {
			expect(left - navigationOvershoot(left, 460, 1400, 320)).toBeGreaterThanOrEqual(0);
		}
	});
});

describe("a dragged standing window", () => {
	const viewport = { width: 1400, height: 800 };

	it("stops at the navigation's edge on the right, and at the margin with none", () => {
		const far = { left: 5000, bottom: 100 };
		expect(clampPlacement(far, viewport, 300).left).toBe(1400 - MARGIN - 300);

		navInsetRight.value = 274;
		expect(clampPlacement(far, viewport, 300).left).toBe(1400 - 274 - MARGIN - 300);
		navInsetRight.value = 0;
	});
});

describe("navigationShift", () => {
	const insets = { left: 274, right: 0 };

	it("pulls a float out from under a navigation on the left", () => {
		expect(navigationShift(100, 460, 1400, insets)).toBe(174);
		expect(navigationShift(274, 460, 1400, insets)).toBe(0);
		expect(navigationShift(600, 460, 1400, insets)).toBe(0);
	});

	it("keeps the right-hand rule, and the left edge wins for a float wider than the room", () => {
		expect(navigationShift(940, 460, 1400, { left: 0, right: 320 })).toBe(-320);
		expect(navigationShift(0, 900, 1000, { left: 274, right: 320 })).toBe(274);
	});
});
