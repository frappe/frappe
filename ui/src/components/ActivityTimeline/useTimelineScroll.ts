import { nextTick, onMounted, ref, watch, type Ref } from "vue";

/**
 * Owns timeline scroll behavior when paging is on: finds the scrollable ancestor,
 * opens at the bottom (newest) once, and keeps the viewport fixed when older rows
 * prepend on Load More. `captureAnchor(key)` records the anchor offset before
 * fetching older rows so the next length change can restore it.
 */
export function useTimelineScroll(
  rootEl: Ref<HTMLElement | null>,
  activityCount: Ref<number>,
  isEnabled: () => boolean
) {
  const scrollEl = ref<HTMLElement | null>(null);

  // anchor = a visible row's key + its top offset within the scroll container
  let anchorKey: string | null = null;
  let anchorOffset = 0;
  let didInitialScroll = false;

  const findRow = (key: string) =>
    rootEl.value?.querySelector<HTMLElement>(`[id="${CSS.escape(key)}"]`) ?? null;

  const offsetWithin = (el: HTMLElement, container: HTMLElement) =>
    el.getBoundingClientRect().top - container.getBoundingClientRect().top;

  function captureAnchor(key: string | null) {
    const container = scrollEl.value;
    const row = container && key ? findRow(key) : null;
    if (container && row && key) {
      anchorKey = key;
      anchorOffset = offsetWithin(row, container);
    }
  }

  // re-pin the anchor after older rows patch in, so the viewport doesn't jump
  function restoreAnchor() {
    const container = scrollEl.value;
    if (!container || anchorKey === null) return;
    const key = anchorKey;
    nextTick(() => {
      const row = findRow(key);
      if (row) container.scrollTop += offsetWithin(row, container) - anchorOffset;
      anchorKey = null;
    });
  }

  // oldest-first feed: open at the bottom (newest) on first render, once
  function scrollToBottomOnce() {
    if (didInitialScroll || !activityCount.value) return;
    const container = scrollEl.value;
    if (!container) return;
    didInitialScroll = true;
    nextTick(() => {
      container.scrollTop = container.scrollHeight;
    });
  }

  onMounted(() => {
    scrollEl.value = findScrollableAncestor(rootEl.value);
    if (isEnabled()) scrollToBottomOnce();
  });

  watch(activityCount, () => {
    if (!isEnabled()) return;
    restoreAnchor();
    scrollToBottomOnce();
  });

  return { scrollEl, captureAnchor };
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
