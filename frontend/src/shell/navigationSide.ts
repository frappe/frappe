// Which edge the navigation (rail and sidebar) is drawn on. The stored value is `start` or `end`;
// only this file turns it into a physical `left` or `right`, from the page's text direction.
import { ref } from "vue";
import { __ } from "@/i18n";

export type NavigationSide = "start" | "end";
export type PhysicalSide = "left" | "right";

/** The side in force: the person's own, else the site's, else `start`. Set by `seedNavigationSide` and by a save. */
export const navigationSide = ref<NavigationSide>("start");

/** Reads the person's and the site's values from the boot's session; an unknown value counts as blank. */
export function seedNavigationSide(session: {
	user: { navigation_side?: string };
	defaults?: Record<string, unknown>;
}) {
	navigationSide.value = firstSide(session.user.navigation_side, session.defaults?.navigation_side);
}

function firstSide(...values: unknown[]): NavigationSide {
	return (values.find((value) => value === "start" || value === "end") as NavigationSide) ?? "start";
}

/** `start` is where a line of text starts: left in LTR, right in RTL. */
export function physicalSide(side: NavigationSide, dir: string): PhysicalSide {
	return (side === "start") === (dir !== "rtl") ? "left" : "right";
}

export function sideLabel(side: NavigationSide, dir: string): string {
	return physicalSide(side, dir) === "left" ? __("Left") : __("Right");
}

/** Plain functions, not computeds: `dir` is a DOM attribute, which Vue does not track. */
export function navSide(): PhysicalSide {
	return physicalSide(navigationSide.value, document.documentElement.dir);
}

/** The side that points away from the navigation: where its tooltips and menus open. */
export function awaySide(): PhysicalSide {
	return navSide() === "left" ? "right" : "left";
}
