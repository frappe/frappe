// The record page's scroll boxes as the view keeps them: the shown tab body and each body column.
import { landScroll } from "@framework/ui/utils/scrollLanding";
import type { RecordView } from "./viewMemory";

type Offsets = RecordView["offsets"];

export function readOffsets(root: HTMLElement, tab: string): Offsets {
  const columns: Record<string, number> = {};
  for (const [name, scroller] of columnScrollers(root)) columns[name] = scroller.scrollTop;
  const body = tabScroller(root, tab);
  return body ? { tab: body.scrollTop, columns } : { columns };
}

/** Sets each box as its content allows; answers when all have landed. */
export function landOffsets(root: HTMLElement, tab: string, offsets: Offsets): Promise<void> {
  const boxes = columnScrollers(root);
  const landings = Object.entries(offsets.columns).map(([name, top]) => land(boxes.get(name), top));
  if (offsets.tab !== undefined) landings.push(land(tabScroller(root, tab), offsets.tab));
  return Promise.all(landings).then(() => {});
}

function land(element: HTMLElement | null | undefined, top: number) {
  return element ? landScroll(element, top) : Promise.resolve();
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
