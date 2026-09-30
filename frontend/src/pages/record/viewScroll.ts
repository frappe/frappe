// The record page's scroll boxes as the view keeps them: the shown tab body and each body column.
import type { RecordView } from "./viewMemory";

const LANDING_FRAMES = 60;

type Offsets = RecordView["offsets"];

export function readOffsets(root: HTMLElement, tab: string): Offsets {
  const columns: Record<string, number> = {};
  for (const [name, scroller] of columnScrollers(root)) columns[name] = scroller.scrollTop;
  const body = tabScroller(root, tab);
  return body ? { tab: body.scrollTop, columns } : { columns };
}

/** Sets each box at once, or over the frames its content takes to grow; answers when all have landed. */
export function landOffsets(root: HTMLElement, tab: string, offsets: Offsets): Promise<void> {
  const boxes = columnScrollers(root);
  const landings = Object.entries(offsets.columns).map(([name, top]) => land(boxes.get(name), top));
  if (offsets.tab !== undefined) landings.push(land(tabScroller(root, tab), offsets.tab));
  return Promise.all(landings).then(() => {});
}

/** Calls `saw` once per frame while any box under the root scrolls. */
export function onScrollFrames(root: HTMLElement, saw: () => void): () => void {
  let frame = 0;
  const scrolled = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(saw);
  };
  // Capture: a scroll event does not bubble.
  root.addEventListener("scroll", scrolled, { capture: true, passive: true });
  return () => {
    cancelAnimationFrame(frame);
    root.removeEventListener("scroll", scrolled, { capture: true });
  };
}

function land(element: HTMLElement | null | undefined, top: number): Promise<void> {
  if (!element) return Promise.resolve();
  return new Promise((resolve) => {
    let frames = LANDING_FRAMES;
    const attempt = () => {
      const fits = element.scrollHeight - element.clientHeight >= top;
      if (!fits && frames-- > 0) return void requestAnimationFrame(attempt);
      element.scrollTop = top;
      resolve();
    };
    attempt();
  });
}

function columnScrollers(root: HTMLElement): Map<string, HTMLElement> {
  const scrollers = new Map<string, HTMLElement>();
  for (const column of root.querySelectorAll<HTMLElement>("[data-body-column]")) {
    const scroller = column.querySelector<HTMLElement>(":scope > [data-body-scroll]");
    if (scroller) scrollers.set(column.dataset.bodyColumn!, scroller);
  }
  return scrollers;
}

/** The body's own scroller: the first scroll area in it, which a feed tab draws too. */
function tabScroller(root: HTMLElement, tab: string): HTMLElement | null {
  return root.querySelector<HTMLElement>(
    `[data-record-tab="${CSS.escape(tab)}"] [data-slot="scroll-area-viewport"]`,
  );
}
