import { nextTick, onMounted, watch } from "vue";
import type { Ref } from "vue";

/** 20px lines inside 4px of padding above and below: one line is 28. */
export const LINE_HEIGHT = 20;
export const PADDING = 8;
export const MAX_LINES = 6;
export const MAX_HEIGHT = PADDING + LINE_HEIGHT * MAX_LINES;

/** Sizes `el` to its content, from one line up to `MAX_HEIGHT`: on mount and whenever `source` changes. */
export function useTextareaGrow(el: Ref<HTMLElement | null>, source: () => unknown, enabled: () => boolean) {
  function fit() {
    const box = el.value;
    if (!box) return;
    const scrolled = box.scrollTop;
    box.style.height = "auto";
    box.scrollTop = scrolled;
    box.style.height = `${Math.min(box.scrollHeight, MAX_HEIGHT)}px`;
  }
  onMounted(() => enabled() && fit());
  watch(source, () => enabled() && nextTick(fit));
}
