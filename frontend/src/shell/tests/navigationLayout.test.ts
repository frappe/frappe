// The draw mode: every cell of the spec's table, and the store a navigation payload fills.
import { afterEach, describe, expect, it } from "vitest";
import type { NavigationLayout } from "@/boot";
import { applyNavigationLayout, canPin, drawMode, navigationLayout, pinned } from "../navigationLayout";
import type { DrawMode, WidthBand } from "../navigationLayout";

afterEach(() => applyNavigationLayout({ navigation_layout: "rail_and_sidebar" }));

describe("drawMode", () => {
	const table: [WidthBand, boolean, Record<NavigationLayout, DrawMode>][] = [
		["wide", true, { rail_and_sidebar: "rail", sidebar_only: "sidebar_only", floating_rail: "floating" }],
		["wide", false, { rail_and_sidebar: "rail", sidebar_only: "sidebar_only", floating_rail: "rail" }],
		["narrow", true, { rail_and_sidebar: "rail_overlay", sidebar_only: "drawer", floating_rail: "drawer" }],
		["narrow", false, { rail_and_sidebar: "rail_overlay", sidebar_only: "drawer", floating_rail: "drawer" }],
		["phone", true, { rail_and_sidebar: "phone", sidebar_only: "phone", floating_rail: "phone" }],
		["phone", false, { rail_and_sidebar: "phone", sidebar_only: "phone", floating_rail: "phone" }],
	];

	for (const [band, canHover, modes] of table) {
		for (const [layout, mode] of Object.entries(modes)) {
			it(`${layout} is ${mode} when ${band}, ${canHover ? "with" : "without"} hover`, () => {
				expect(drawMode(layout as NavigationLayout, band, canHover)).toBe(mode);
			});
		}
	}
});

describe("applyNavigationLayout", () => {
	it("takes the layout and the pin off a payload", () => {
		applyNavigationLayout({ navigation_layout: "floating_rail", pinned: true });
		expect([navigationLayout.value, pinned.value]).toEqual(["floating_rail", true]);

		applyNavigationLayout({ navigation_layout: "sidebar_only" });
		expect([navigationLayout.value, pinned.value]).toEqual(["sidebar_only", false]);
	});

	it("takes the right to pin off a payload", () => {
		applyNavigationLayout({ navigation_layout: "floating_rail", can_pin: true });
		expect(canPin.value).toBe(true);

		applyNavigationLayout({ navigation_layout: "floating_rail" });
		expect(canPin.value).toBe(false);
	});
});
