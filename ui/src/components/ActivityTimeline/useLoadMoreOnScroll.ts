import { useInfiniteScroll } from "@vueuse/core";
import { onMounted, ref, type Ref } from "vue";
import type { InfiniteScrollControls } from "./types";

// px from the bottom of the scroll container at which to fetch the next page
const SCROLL_DISTANCE = 400;

/**
 Calls `controls().fetchNextPage()` when `rootEl`'s nearest scrollable ancestor
 */
export function useLoadMoreOnScroll(
  rootEl: Ref<HTMLElement | null>,
  controls: () => InfiniteScrollControls | undefined,
  distance: number = SCROLL_DISTANCE
) {
  const target = ref<HTMLElement | Window | null>(null);
  onMounted(() => {
    target.value = findScrollParent(rootEl.value);
  });

  useInfiniteScroll(
    target,
    () => {
      const c = controls();
      if (!c?.hasNextPage || c.isFetchingNextPage) return;
      return c.fetchNextPage?.();
    },
    { distance }
  );
}

// Resolve the nearest scrollable ancestor; fall back to the window. VueUse needs
// the scroll element directly — it does not walk ancestors.
function findScrollParent(el: HTMLElement | null): HTMLElement | Window {
  let node = el?.parentElement ?? null;
  while (node) {
    const overflowY = getComputedStyle(node).overflowY;
    if (
      overflowY === "auto" ||
      overflowY === "scroll" ||
      overflowY === "overlay"
    ) {
      return node;
    }
    node = node.parentElement;
  }
  return window;
}
