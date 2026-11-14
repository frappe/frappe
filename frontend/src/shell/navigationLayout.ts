// How the navigation draws: the layout the person's levels resolve to, the window's width and
// whether the device can hover, folded into one draw mode. The draw mode is never stored.
import { breakpointsTailwind, useBreakpoints, useMediaQuery } from "@vueuse/core";
import { computed, ref } from "vue";
import type { Navigation, NavigationLayout } from "@/boot";

export type WidthBand = "phone" | "narrow" | "wide";
export type DrawMode =
	| "rail"
	| "sidebar_only"
	| "floating"
	| "rail_overlay"
	| "drawer"
	| "phone";

/** The layout in force, from the boot and replaced by every `resolve_navigation` response. */
export const navigationLayout = ref<NavigationLayout>("rail_and_sidebar");

/** True only for a person's own rail + sidebar over an inherited floating rail: the unpin button shows. */
export const pinned = ref(false);

/** Takes the layout and the pin off a `Navigation` payload: the boot's, or a save's. */
export function applyNavigationLayout(navigation: Pick<Navigation, "navigation_layout" | "pinned">) {
	navigationLayout.value = navigation.navigation_layout;
	pinned.value = navigation.pinned === true;
}

const NARROW: Record<NavigationLayout, DrawMode> = {
	rail_and_sidebar: "rail_overlay",
	sidebar_only: "drawer",
	floating_rail: "drawer",
};

/** The pure rule behind `useDrawMode`. A floating rail needs a pointer to reveal it, so without hover it draws as the rail. */
export function drawMode(layout: NavigationLayout, band: WidthBand, canHover: boolean): DrawMode {
	if (band === "phone") return "phone";
	if (band === "narrow") return NARROW[layout];
	if (layout === "sidebar_only") return "sidebar_only";
	return layout === "floating_rail" && canHover ? "floating" : "rail";
}

/** The draw mode now, following the window's width and the device's pointer. Call it from a component. */
export function useDrawMode() {
	const breakpoints = useBreakpoints(breakpointsTailwind);
	const wide = breakpoints.greaterOrEqual("lg");
	const notPhone = breakpoints.greaterOrEqual("md");
	const canHover = useMediaQuery("(any-hover: hover)");

	// `phone` below 768 px, `narrow` below 1024 px.
	const widthBand = computed<WidthBand>(() =>
		wide.value ? "wide" : notPhone.value ? "narrow" : "phone"
	);
	const mode = computed(() => drawMode(navigationLayout.value, widthBand.value, canHover.value));

	return { widthBand, canHover, drawMode: mode };
}
