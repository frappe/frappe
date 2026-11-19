/** The parts of Floating UI's middleware state the limiter reads. */
type LimiterState = {
  x: number;
  y: number;
  rects: { reference: { x: number }; floating: { width: number } };
  elements: { reference: { getBoundingClientRect(): { left: number } } };
};

/** Where a bar `width` wide starts: at `left`, inside `minLeft`..`maxRight`; the right edge wins. */
export function clampBarLeft(left: number, width: number, minLeft: number, maxRight: number) {
  return Math.min(Math.max(left, minLeft), maxRight - width);
}

/** A Floating UI `shift` limiter: the bar centres on the selection but stays inside `box`. */
export function keepBarInBox(box: () => HTMLElement | null | undefined) {
  return {
    fn(state: LimiterState) {
      const rect = box()?.getBoundingClientRect();
      if (!rect) return { x: state.x, y: state.y };
      const toViewport =
        state.elements.reference.getBoundingClientRect().left - state.rects.reference.x;
      const left = clampBarLeft(
        state.x + toViewport,
        state.rects.floating.width,
        rect.left,
        rect.right
      );
      return { x: left - toViewport, y: state.y };
    },
  };
}
