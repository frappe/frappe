/** The parts of Floating UI's middleware state the limiter reads. */
type LimiterState = {
  x: number;
  y: number;
  rects: { reference: { x: number }; floating: { width: number } };
  elements: { reference: { getBoundingClientRect(): { left: number } } };
};

/** Where a bar `width` wide starts: at `left`, not before `minLeft`, and never past `maxRight`. */
export function clampBarLeft(left: number, width: number, minLeft: number, maxRight: number) {
  return Math.min(Math.max(left, minLeft), maxRight - width);
}

/**
 * A Floating UI `shift` limiter: the bar starts no further left than `box`, unless that would
 * push it past the panel's right edge (`[data-picker-bound]`) or the viewport's.
 */
export function keepBarInBox(box: () => HTMLElement | null | undefined) {
  return {
    fn(state: LimiterState) {
      const el = box();
      if (!el) return { x: state.x, y: state.y };
      const bound = el.closest("[data-picker-bound]")?.getBoundingClientRect().right ?? Infinity;
      const toViewport =
        state.elements.reference.getBoundingClientRect().left - state.rects.reference.x;
      const left = clampBarLeft(
        state.x + toViewport,
        state.rects.floating.width,
        el.getBoundingClientRect().left,
        Math.min(bound, document.documentElement.clientWidth)
      );
      return { x: left - toViewport, y: state.y };
    },
  };
}
