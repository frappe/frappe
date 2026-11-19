// Follows a scroll viewport: whether it scrolls, and which sections show in it.
import { ref, shallowRef } from "vue";

export interface MarkedSection {
  key: string;
  label: string;
  description?: string;
}

/** The sections that show in a viewport of `height`, from their edges measured from its top. */
export function sectionsInView(
  edges: { key: string; top: number; bottom: number }[],
  height: number
): Set<string> {
  return new Set(edges.filter(({ top, bottom }) => bottom > 0 && top < height).map(({ key }) => key));
}

export class SectionTracker {
  readonly inView = shallowRef(new Set<string>());
  readonly scrolls = ref(false);
  private resize = new ResizeObserver(() => this.measure());
  private frame = 0;

  constructor(
    readonly viewport: HTMLElement,
    private sections: () => MarkedSection[],
    private find: (key: string) => HTMLElement | null
  ) {
    viewport.addEventListener("scroll", this.onScroll, { passive: true });
    this.resize.observe(viewport);
    // The viewport keeps its size while its content grows, as blocks load.
    for (const child of viewport.children) this.resize.observe(child);
    this.measure();
  }

  stop() {
    this.viewport.removeEventListener("scroll", this.onScroll);
    this.resize.disconnect();
    cancelAnimationFrame(this.frame);
  }

  measure() {
    const { scrollHeight, clientHeight } = this.viewport;
    this.scrolls.value = scrollHeight > clientHeight + 1;
    const top = this.viewport.getBoundingClientRect().top;
    const edges = [];
    for (const { key } of this.sections()) {
      const rect = this.find(key)?.getBoundingClientRect();
      if (rect) edges.push({ key, top: rect.top - top, bottom: rect.bottom - top });
    }
    this.inView.value = sectionsInView(edges, clientHeight);
  }

  private onScroll = () => {
    cancelAnimationFrame(this.frame);
    this.frame = requestAnimationFrame(() => this.measure());
  };
}
