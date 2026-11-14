// How far the in-flow navigation reaches in from the window's right edge. Fixed-position floats
// (toasts, the composer, the standing windows, the bulk tray, Flow) add it to their right offset, so
// they sit at the content area's bottom-right corner and never cover the rail's foot or its avatar.
import { useElementBounding } from "@vueuse/core";
import { computed, onBeforeUnmount, shallowRef, watchEffect, type Ref } from "vue";
import { navSide } from "./navigationSide";

export const NAV_INSET_RIGHT = "--shell-nav-inset-right";

/** The rail's width, plus the sidebar's while it is open, when the navigation is on the right; else 0. */
export const navInsetRight = shallowRef(0);

/** Keeps `navInsetRight` and the CSS variable on `:root` in step with the shell's content element. */
export function useNavigationInset(content: Ref<HTMLElement | null | undefined>) {
	const { width } = useElementBounding(content);
	const inset = computed(() =>
		navSide() === "right" && content.value
			? Math.max(0, Math.round(document.documentElement.clientWidth - width.value))
			: 0
	);

	watchEffect(() => {
		navInsetRight.value = inset.value;
		document.documentElement.style.setProperty(NAV_INSET_RIGHT, `${inset.value}px`);
	});

	onBeforeUnmount(() => {
		navInsetRight.value = 0;
		document.documentElement.style.removeProperty(NAV_INSET_RIGHT);
	});
}
