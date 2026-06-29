import { onMounted, ref, type Ref } from "vue";

// Nearest scrollable ancestor of `rootEl`, so the timeline can park at the bottom on first render.
export function useScrollContainer(rootEl: Ref<HTMLElement | null>) {
  const scrollEl = ref<HTMLElement | null>(null);

  onMounted(() => {
    scrollEl.value = findScrollableAncestor(rootEl.value);
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
