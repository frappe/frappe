// The docked card's height: a drag from the top edge, clamped to the window, kept per user.
import { afterEach, describe, expect, it } from "vitest";
import { effectScope, nextTick } from "vue";
import {
	clampDockHeight,
	DEFAULT_DOCK_HEIGHT,
	MIN_DOCK_HEIGHT,
	useDockHeight,
} from "../useDockHeight";

const scopes: ReturnType<typeof effectScope>[] = [];

afterEach(() => {
	for (const scope of scopes.splice(0)) scope.stop();
	localStorage.clear();
});

function dock(user: string) {
	const scope = effectScope();
	scopes.push(scope);
	return scope.run(() => useDockHeight(user))!;
}

const pointer = (clientY: number) =>
	({ clientY, pointerId: 1, currentTarget: null } as unknown as PointerEvent);

describe("the docked height", () => {
	it("grows as the handle goes up and keeps the height under the user's own key", async () => {
		const ann = dock("ann@example.com");
		expect(ann.height.value).toBe(DEFAULT_DOCK_HEIGHT);
		ann.begin(pointer(500), DEFAULT_DOCK_HEIGHT);
		ann.move(pointer(400));
		ann.end();
		ann.move(pointer(0));
		await nextTick();
		expect(ann.height.value).toBe(DEFAULT_DOCK_HEIGHT + 100);
		expect(localStorage.getItem("desk:composer-height:ann@example.com")).toBe(
			String(DEFAULT_DOCK_HEIGHT + 100)
		);
		expect(dock("bob@example.com").height.value).toBe(DEFAULT_DOCK_HEIGHT);
	});

	it("never shrinks past the editor nor outgrows most of the window", () => {
		expect(clampDockHeight(20, 1000)).toBe(MIN_DOCK_HEIGHT);
		expect(clampDockHeight(5000, 1000)).toBe(720);
		expect(clampDockHeight(5000, 100)).toBe(MIN_DOCK_HEIGHT);
	});

	it("falls back to the default height for a stored value that is not a number", () => {
		localStorage.setItem("desk:composer-height:ann@example.com", "tall");
		expect(dock("ann@example.com").height.value).toBe(DEFAULT_DOCK_HEIGHT);
	});
});
