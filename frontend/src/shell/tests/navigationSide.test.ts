// The navigation side: which physical edge `start` and `end` mean, and the store the boot seeds.
import { afterEach, describe, expect, it } from "vitest";
import {
	awaySide,
	navigationSide,
	navSide,
	physicalSide,
	seedNavigationSide,
	setOwnNavigationSide,
	setSiteNavigationSide,
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

describe("a save from the settings dialog", () => {
	it("a person's value wins over the site's, and a blank one follows it", () => {
		seedNavigationSide(session("", "start"));
		setOwnNavigationSide("end");
		expect(navigationSide.value).toBe("end");
		setSiteNavigationSide("end");
		setOwnNavigationSide("start");
		expect(navigationSide.value).toBe("start");
		setOwnNavigationSide("");
		expect(navigationSide.value).toBe("end");
	});

	it("a site value moves a person with none of their own and no one else", () => {
		seedNavigationSide(session("", "start"));
		setSiteNavigationSide("end");
		expect(navigationSide.value).toBe("end");
		setOwnNavigationSide("start");
		setSiteNavigationSide("start");
		setSiteNavigationSide("end");
		expect(navigationSide.value).toBe("start");
	});
});

describe("sideLabel", () => {
	it.each([
		["start", "", "Left"],
		["end", "", "Right"],
		["start", "rtl", "Right"],
		["end", "rtl", "Left"],
	] as const)("%s in %s reads %s", (side, dir, expected) => {
		if (dir) document.documentElement.setAttribute("dir", dir);
		expect(sideLabel(side)).toBe(expected);
	});
});
