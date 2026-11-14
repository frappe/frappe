// The navigation side: which physical edge `start` and `end` mean, and the store the boot seeds.
import { afterEach, describe, expect, it } from "vitest";
import {
	awaySide,
	navigationSide,
	navSide,
	physicalSide,
	seedNavigationSide,
	sideLabel,
	type NavigationSide,
} from "../navigationSide";

const session = (own: string | undefined, site?: string) => ({
	user: { navigation_side: own },
	defaults: site === undefined ? {} : { navigation_side: site },
});

afterEach(() => {
	document.documentElement.removeAttribute("dir");
	navigationSide.value = "start";
});

describe("physicalSide", () => {
	it.each([
		["start", "ltr", "left"],
		["end", "ltr", "right"],
		["start", "rtl", "right"],
		["end", "rtl", "left"],
		["start", "", "left"],
	] as const)("%s in %s is %s", (side, dir, expected) => {
		expect(physicalSide(side, dir)).toBe(expected);
	});
});

describe("the seed", () => {
	// blank / start / end for the person, start / end for the site, both text directions.
	it.each([
		["", "start", "start"],
		["", "end", "end"],
		["start", "end", "start"],
		["end", "start", "end"],
		["end", "end", "end"],
		["start", "start", "start"],
		[undefined, undefined, "start"],
	] as const)("a person's %s over the site's %s reads %s", (own, site, expected) => {
		seedNavigationSide(session(own, site));
		expect(navigationSide.value).toBe(expected);
	});

	it("reads a missing or unknown value as the next one down", () => {
		seedNavigationSide(session("sideways", "end"));
		expect(navigationSide.value).toBe("end");
		seedNavigationSide({ user: {} });
		expect(navigationSide.value).toBe("start");
	});

	it.each([
		["", "start", "ltr", "left"],
		["", "end", "ltr", "right"],
		["end", "start", "ltr", "right"],
		["start", "end", "ltr", "left"],
		["", "start", "rtl", "right"],
		["", "end", "rtl", "left"],
		["end", "start", "rtl", "left"],
		["start", "end", "rtl", "right"],
	])("a person's %s over the site's %s in %s draws on the %s", (own, site, dir, expected) => {
		document.documentElement.dir = dir;
		seedNavigationSide(session(own, site));
		expect(navSide()).toBe(expected);
		expect(awaySide()).toBe(expected === "left" ? "right" : "left");
	});
});

describe("sideLabel", () => {
	it.each([
		["start", "ltr", "Left"],
		["end", "ltr", "Right"],
		["start", "rtl", "Right"],
		["end", "rtl", "Left"],
	] as [NavigationSide, string, string][])("%s in %s reads %s", (side, dir, label) => {
		expect(sideLabel(side, dir)).toBe(label);
	});
});
