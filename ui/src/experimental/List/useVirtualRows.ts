import { useElementSize, useEventListener } from "@vueuse/core";
import { computed, ref, toValue, watch, type MaybeRefOrGetter } from "vue";

export interface UseVirtualRowsOptions {
  /** Row height in px. */
  rowHeight: MaybeRefOrGetter<number>;
  /** Rows rendered beyond the visible window on each side. */
  overscan?: MaybeRefOrGetter<number>;
  /** The element that scrolls the rows. */
  scrollContainer: MaybeRefOrGetter<HTMLElement | null | undefined>;
}

/** Windowing over a scroll container the caller names; frappe-ui's `ListRows virtual` reads its container once at mount and finds none inside a ScrollArea. */
export function useVirtualRows<T>(
  items: MaybeRefOrGetter<T[]>,
  options: UseVirtualRowsOptions,
) {
  const source = computed(() => toValue(items));
  const container = computed(() => toValue(options.scrollContainer) ?? null);
  const scrollTop = ref(0);
  const { height: viewportHeight } = useElementSize(container);

  watch(container, (el) => (scrollTop.value = el?.scrollTop ?? 0), {
    immediate: true,
  });

  useEventListener(container, "scroll", () => {
    scrollTop.value = container.value?.scrollTop ?? 0;
  });

  const range = computed(() => {
    const rowHeight = Math.max(1, toValue(options.rowHeight));
    const overscan = Math.max(0, Math.floor(toValue(options.overscan ?? 6)));
    const visibleStart = Math.floor(scrollTop.value / rowHeight);
    const visibleEnd = Math.ceil(
      (scrollTop.value + viewportHeight.value) / rowHeight,
    );
    const start = Math.max(0, visibleStart - overscan);
    const end = Math.min(source.value.length, visibleEnd + overscan);
    return { start, end, rowHeight };
  });

  const rows = computed(() =>
    source.value
      .slice(range.value.start, range.value.end)
      .map((data, index) => ({ data, index: index + range.value.start })),
  );

  const wrapperProps = computed(() => {
    const offset = range.value.start * range.value.rowHeight;
    const total = source.value.length * range.value.rowHeight;
    return {
      style: {
        width: "100%",
        height: `${total - offset}px`,
        marginTop: `${offset}px`,
      },
    };
  });

  return { rows, wrapperProps };
}
