import { nextTick, onMounted, onUnmounted, watch, type Ref } from "vue";

/**
 * Owns timeline scroll behavior when paging is on: finds the scrollable ancestor,
 * opens at the bottom (newest) once, and keeps the viewport fixed when older rows
 * prepend on Load More. `captureAnchor(key)` records the anchor offset before
 * fetching older rows so the next length change can restore it.
 *
 * The scroll container is resolved lazily on every use (not cached at mount): under
 * force-mounted tab panels the timeline can mount hidden, where no ancestor is
 * scrollable yet. A ResizeObserver retries the one-time initial scroll when the
 * hidden panel gains size.
 */
export function useTimelineScroll(
  rootEl: Ref<HTMLElement | null>,
  activityCount: Ref<number>,
  isEnabled: () => boolean
) {
  // anchor = a visible row's key + its top offset within the scroll container
  let anchorKey: string | null = null;
  let anchorOffset = 0;
  let didInitialScroll = false;

  const scrollEl = () => findScrollableAncestor(rootEl.value);

  const findRow = (key: string) =>
    rootEl.value?.querySelector<HTMLElement>(`[id="${CSS.escape(key)}"]`) ??
    null;

  const offsetWithin = (el: HTMLElement, container: HTMLElement) =>
    el.getBoundingClientRect().top - container.getBoundingClientRect().top;

  function captureAnchor(key: string | null) {
    const container = scrollEl();
    const row = container && key ? findRow(key) : null;
    if (container && row && key) {
      anchorKey = key;
      anchorOffset = offsetWithin(row, container);
    }
  }

  // re-pin the anchor after older rows patch in, so the viewport doesn't jump
  function restoreAnchor() {
    if (anchorKey === null) return;
    const key = anchorKey;
    nextTick(() => {
      const container = scrollEl();
      const row = container ? findRow(key) : null;
      if (container && row)
        container.scrollTop += offsetWithin(row, container) - anchorOffset;
      anchorKey = null;
    });
  }

  // explicit jump to newest; hidden/tabbed layouts call this on reveal
  function scrollToLatest() {
    const container = scrollEl();
    if (!container) return;
    didInitialScroll = true; // satisfies the one-time auto-scroll
    container.scrollTop = container.scrollHeight;
  }

  // oldest-first feed: open at the bottom (newest) on first render, once
  function scrollToBottomOnce() {
    if (didInitialScroll || !activityCount.value) return;
    // hidden (display:none panel) → offsetParent is null; retry via the observer
    if (!rootEl.value?.offsetParent) return;
    const container = scrollEl();
    // nothing scrollable yet (rows/images still laying out) — don't consume the
    // one-time scroll on a no-op; the observer and count watcher retry
    if (!container || container.scrollHeight <= container.clientHeight) return;
    didInitialScroll = true;
    container.scrollTop = container.scrollHeight;
  }

  // content grows after the initial scroll (email iframes, images) — while the
  // user is still near the bottom, keep them pinned there; never yank if they
  // scrolled up to read
  function repinBottom() {
    if (!didInitialScroll) return;
    const container = scrollEl();
    if (!container) return;
    const fromBottom =
      container.scrollHeight - container.clientHeight - container.scrollTop;
    if (fromBottom > 0 && fromBottom < 200)
      container.scrollTop = container.scrollHeight;
  }

  const resizeObserver =
    typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(() => {
          if (!isEnabled()) return;
          scrollToBottomOnce();
          repinBottom();
        });

  onMounted(() => {
    if (rootEl.value) resizeObserver?.observe(rootEl.value);
    if (isEnabled()) scrollToBottomOnce();
  });
  onUnmounted(() => resizeObserver?.disconnect());

  watch(
    activityCount,
    () => {
      if (!isEnabled()) return;
      restoreAnchor();
      scrollToBottomOnce();
    },
    // post: measure after the new rows are in the DOM, not before
    { flush: "post" }
  );

  return { captureAnchor, scrollToLatest };
}

// Nearest visible scrollable ancestor; falls back to the document scroller.
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
