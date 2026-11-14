// How far the navigation reaches in from the window's edge it is drawn on. Fixed-position floats keep
// clear of it, so they sit at the content area's corner and never cover the rail.
import { useElementBounding } from "@vueuse/core";
import { computed, onBeforeUnmount, shallowRef, watch, watchEffect, type Ref } from "vue";
import { navSide } from "./navigationSide";

export const NAV_INSET_RIGHT = "--shell-nav-inset-right";
export const NAV_INSET_BOTTOM = "--shell-nav-inset-bottom";

/** The tab bar's height, safe area included, while the phone navigation draws, else 0: floats add it to their bottom offset. */
export const navInsetBottom = shallowRef(0);

/** The rail's width, plus the sidebar's while it is open, when the navigation is on the right; else 0. */
export const navInsetRight = shallowRef(0);

/** The same, from the window's left edge, when the navigation is on the left. */
export const navInsetLeft = shallowRef(0);

/** Keeps both insets and the CSS variable on `:root` in step with the shell's content element. */
export function useNavigationInset(
	content: Ref<HTMLElement | null | undefined>,
	phone: Ref<boolean> = shallowRef(false)
) {
	const { width } = useElementBounding(content);
	// The content ends at the window's other edge, so what it leaves of the width is the navigation's,
	// whichever side it is on: a side change moves the content without resizing it. The phone draws
	// no side navigation, so it reaches in from no side.
	const reach = computed(() =>
		!phone.value && content.value
			? Math.max(0, Math.round(document.documentElement.clientWidth - width.value))
			: 0
	);
	const inset = computed(() => (navSide() === "right" ? reach.value : 0));
	const insetLeft = computed(() => (navSide() === "left" ? reach.value : 0));

	watchEffect(() => {
		navInsetRight.value = inset.value;
		navInsetLeft.value = insetLeft.value;
		document.documentElement.style.setProperty(NAV_INSET_RIGHT, `${inset.value}px`);
	});

	onBeforeUnmount(() => {
		navInsetRight.value = 0;
		navInsetLeft.value = 0;
		document.documentElement.style.removeProperty(NAV_INSET_RIGHT);
	});
}

/** Keeps `navInsetBottom` and the CSS variable on `:root` at the measured height of the phone tab bar. */
export function useTabBarInset(bar: Ref<HTMLElement | null | undefined>) {
	const { height } = useElementBounding(bar);

	watchEffect(() => {
		const inset = Math.round(height.value);
		navInsetBottom.value = inset;
		document.documentElement.style.setProperty(NAV_INSET_BOTTOM, `${inset}px`);
	});

	onBeforeUnmount(() => {
		navInsetBottom.value = 0;
		document.documentElement.style.removeProperty(NAV_INSET_BOTTOM);
	});
}

/** How far a float at `left`, `width` wide, reaches into the navigation at the end of a viewport; the same sum serves the tab bar, from `top` and `height`. */
export function navigationOvershoot(left: number, width: number, viewport: number, inset: number) {
	return Math.max(0, left - Math.max(0, viewport - inset - width));
}

/** How far a float at `left` reaches into the navigation on the left. */
export function navigationUndershoot(left: number, inset: number) {
	return Math.max(0, inset - left);
}

/** The sideways shift that keeps a float clear of the navigation; the left side wins when the room is short. */
export function navigationShift(
	left: number,
	width: number,
	viewport: number,
	insets: { left: number; right: number }
) {
	const overshoot = navigationOvershoot(left, width, viewport, insets.right);
	const undershoot = navigationUndershoot(left - overshoot, insets.left);
	return undershoot ? undershoot - overshoot : overshoot ? -overshoot : 0;
}

/** Keeps a floating window's card clear of the navigation on either side and of the tab bar at the foot, so a drag or a kept position keeps it whole on screen. Returns the stop. */
export function keepClearOfNavigation(card: HTMLElement) {
	function apply() {
		const shift = navigationShift(
			parseFloat(card.style.left) || 0,
			card.offsetWidth,
			document.documentElement.clientWidth,
			{ left: navInsetLeft.value, right: navInsetRight.value }
		);
		// With no tab bar, a card taller than the window is the window's matter, not the bar's.
		const down = navInsetBottom.value
			? navigationOvershoot(
					parseFloat(card.style.top) || 0,
					card.offsetHeight,
					document.documentElement.clientHeight,
					navInsetBottom.value
				)
			: 0;
		const next = [shift && `translateX(${shift}px)`, down && `translateY(${-down}px)`]
			.filter(Boolean)
			.join(" ");
		if (next !== card.style.transform) card.style.transform = next;
	}

	const observer = new MutationObserver(apply);
	observer.observe(card, { attributes: true, attributeFilter: ["style"] });
	const stopWatch = watch([navInsetRight, navInsetLeft, navInsetBottom], apply, { flush: "post" });
	window.addEventListener("resize", apply);
	apply();

	return () => {
		observer.disconnect();
		stopWatch();
		window.removeEventListener("resize", apply);
		card.style.transform = "";
	};
}
