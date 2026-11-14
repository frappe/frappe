// How far the in-flow navigation reaches in from the window's right edge. Fixed-position floats
// (toasts, the composer, the standing windows, the bulk tray, Flow) add it to their right offset, so
// they sit at the content area's bottom-right corner and never cover the rail's foot or its avatar.
import { useElementBounding } from "@vueuse/core";
import {
  computed,
  onBeforeUnmount,
  shallowRef,
  watch,
  watchEffect,
  type Ref,
} from "vue";
import { navSide } from "./navigationSide";

export const NAV_INSET_RIGHT = "--shell-nav-inset-right";

/** The rail's width, plus the sidebar's while it is open, when the navigation is on the right; else 0. */
export const navInsetRight = shallowRef(0);

/** Keeps `navInsetRight` and the CSS variable on `:root` in step with the shell's content element. */
export function useNavigationInset(
  content: Ref<HTMLElement | null | undefined>,
) {
  const { width } = useElementBounding(content);
  const inset = computed(() =>
    navSide() === "right" && content.value
      ? Math.max(
          0,
          Math.round(document.documentElement.clientWidth - width.value),
        )
      : 0,
  );

  watchEffect(() => {
    navInsetRight.value = inset.value;
    document.documentElement.style.setProperty(
      NAV_INSET_RIGHT,
      `${inset.value}px`,
    );
  });

  onBeforeUnmount(() => {
    navInsetRight.value = 0;
    document.documentElement.style.removeProperty(NAV_INSET_RIGHT);
  });
}

/** How far a float at `left`, `width` wide, reaches into the navigation on the right of a viewport. */
export function navigationOvershoot(
  left: number,
  width: number,
  viewport: number,
  inset: number,
) {
  return Math.max(0, left - Math.max(0, viewport - inset - width));
}

/**
 * Keeps a floating window's drag bounds clear of the navigation on the right. The window's own drag
 * stops at the viewport's edges; this pulls it back by the part that would sit over the navigation, so
 * it stays whole on screen on both sides. Returns the stop.
 */
export function keepClearOfNavigation(card: HTMLElement) {
  let applied = "";
  function apply() {
    const overshoot = navigationOvershoot(
      parseFloat(card.style.left) || 0,
      card.offsetWidth,
      document.documentElement.clientWidth,
      navInsetRight.value,
    );
    const next = overshoot ? `translateX(${-overshoot}px)` : "";
    if (next === applied) return;
    applied = next;
    card.style.transform = next;
  }

  const observer = new MutationObserver(apply);
  observer.observe(card, { attributes: true, attributeFilter: ["style"] });
  const stopWatch = watch(navInsetRight, apply, { flush: "post" });
  window.addEventListener("resize", apply);
  apply();

  return () => {
    observer.disconnect();
    stopWatch();
    window.removeEventListener("resize", apply);
    card.style.transform = "";
  };
}
