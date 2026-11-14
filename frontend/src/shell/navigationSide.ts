// Which edge the navigation (rail and sidebar) is drawn on. The stored value is `start` or `end`;
// only this file turns it into a physical `left` or `right`, from the page's text direction.
import { ref } from "vue";
import { __ } from "@/i18n";

export type NavigationSide = "start" | "end";
export type PhysicalSide = "left" | "right";

/** The side in force: the person's own, else the site's, else `start`. Set by `seedNavigationSide` and by a save. */
export const navigationSide = ref<NavigationSide>("start");

/** The person's own value (`""` when blank) and the site's, kept so a save of either can redraw. */
export const ownNavigationSide = ref<NavigationSide | "">("");
export const siteNavigationSide = ref<NavigationSide>("start");

/** Reads the person's and the site's values from the boot's session; an unknown value counts as blank. */
export function seedNavigationSide(session: {
	user: { navigation_side?: string };
	defaults?: Record<string, unknown>;
}) {
	ownNavigationSide.value = ownSide(session.user.navigation_side);
	siteNavigationSide.value = firstSide(session.defaults?.navigation_side);
	navigationSide.value = firstSide(ownNavigationSide.value, siteNavigationSide.value);
}

/** The settings dialog saved the person's value: the shell redraws at once. */
export function setOwnNavigationSide(value: unknown) {
	ownNavigationSide.value = ownSide(value);
	navigationSide.value = firstSide(ownNavigationSide.value, siteNavigationSide.value);
}

/** The settings dialog saved the site's value: a person with no value of their own follows it. */
export function setSiteNavigationSide(value: unknown) {
	siteNavigationSide.value = firstSide(value);
	navigationSide.value = firstSide(ownNavigationSide.value, siteNavigationSide.value);
}

function ownSide(value: unknown): NavigationSide | "" {
	return value === "start" || value === "end" ? value : "";
}

function firstSide(...values: unknown[]): NavigationSide {
	return (values.find((value) => value === "start" || value === "end") as NavigationSide) ?? "start";
}

/** `start` is where a line of text starts: left in LTR, right in RTL. */
export function physicalSide(side: NavigationSide, dir: string): PhysicalSide {
	return (side === "start") === (dir !== "rtl") ? "left" : "right";
}

/** "Left" or "Right" for the person, by the same mapping as `physicalSide`. */
export function sideLabel(side: NavigationSide): string {
	return physicalSide(side, document.documentElement.dir) === "left" ? __("Left") : __("Right");
}

/** Plain functions, not computeds: `dir` is a DOM attribute, which Vue does not track. */
export function navSide(): PhysicalSide {
	return physicalSide(navigationSide.value, document.documentElement.dir);
}

/** The side that points away from the navigation: where its tooltips and menus open. */
export function awaySide(): PhysicalSide {
	return navSide() === "left" ? "right" : "left";
}
