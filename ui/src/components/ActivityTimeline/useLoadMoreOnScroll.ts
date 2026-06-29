import { useInfiniteScroll } from "@vueuse/core";
import { onMounted, ref, type Ref } from "vue";

interface LoadMoreOptions {
  /** Whether another page can be loaded right now (e.g. hasNextPage && !fetching). */
  canLoadMore: () => boolean;
  /** Kick off the next page fetch. */
  loadMore: () => void;
}

// Reverse infinite scroll: call loadMore() near the top of `rootEl`'s scrollable
// ancestor, which is returned so the caller can scroll-anchor after rows prepend.
export function useLoadMoreOnScroll(
  rootEl: Ref<HTMLElement | null>,
  opts: LoadMoreOptions
) {
  const scrollEl = ref<HTMLElement | null>(null);

  onMounted(() => {
    scrollEl.value = findScrollableAncestor(rootEl.value);
    if (!scrollEl.value) return;
    useInfiniteScroll(
      scrollEl,
      () => {
        if (opts.canLoadMore()) opts.loadMore();
      },
      { direction: "top", distance: 400 }
    );
  });

  return { scrollEl };
}

// Nearest scrollable ancestor; falls back to the element, then the document scroller.
function findScrollableAncestor(el: HTMLElement | null): HTMLElement | null {
  let node = el?.parentElement ?? null;
  while (node) {
    const overflowY = getComputedStyle(node).overflowY;
    if (
      (overflowY === "auto" || overflowY === "scroll") &&
      node.scrollHeight > node.clientHeight
    ) {
      return node;
    }
    node = node.parentElement;
  }
  return el ?? (document.scrollingElement as HTMLElement | null);
}
