import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// happy-dom reports no element size, so the viewport height is driven by hand. Everything
// else in the composable stays real, including the scroll listener.
const viewportHeight = ref(0);
vi.mock("@vueuse/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@vueuse/core")>();
  return { ...actual, useElementSize: () => ({ width: ref(0), height: viewportHeight }) };
});

const { useVirtualRows } = await import("../useVirtualRows");

const ROW_HEIGHT = 40;

function items(count: number) {
  return Array.from({ length: count }, (_, i) => ({ name: `row-${i}` }));
}

function scroller(scrollTop = 0) {
  const el = document.createElement("div");
  el.scrollTop = scrollTop;
  return el;
}

function mount(container: HTMLElement | null, count = 100, overscan = 0) {
  const source = ref(items(count));
  const el = ref(container);
  const { rows, wrapperProps } = useVirtualRows(source, {
    rowHeight: () => ROW_HEIGHT,
    overscan: () => overscan,
    scrollContainer: () => el.value,
  });
  return { rows, wrapperProps, el, source };
}

describe("useVirtualRows", () => {
  beforeEach(() => {
    viewportHeight.value = 200;
  });

  it("windows the rows the named container shows", () => {
    const { rows } = mount(scroller());
    expect(rows.value[0].index).toBe(0);
    expect(rows.value.at(-1)!.index).toBe(4);
  });

  it("follows that container as it scrolls", async () => {
    const el = scroller();
    const { rows } = mount(el);
    el.scrollTop = 400;
    el.dispatchEvent(new Event("scroll"));
    await Promise.resolve();
    expect(rows.value[0].index).toBe(10);
  });

  it("reads a container that is already scrolled when it arrives", async () => {
    const { rows, el } = mount(null);
    el.value = scroller(400);
    await new Promise((resolve) => setTimeout(resolve));
    // No scroll event fires here: a container handed over mid-scroll must still window
    // from where it stands, or every row below the fold is missing until the user moves.
    expect(rows.value[0].index).toBe(10);
  });

  it("keeps the scrollbar sized to every row, mounted or not", () => {
    const el = scroller(400);
    const { wrapperProps } = mount(el);
    el.dispatchEvent(new Event("scroll"));
    const { height, marginTop } = wrapperProps.value.style;
    expect(parseInt(marginTop) + parseInt(height)).toBe(100 * ROW_HEIGHT);
  });

  it("renders the overscan on both sides of the window", async () => {
    const el = scroller(400);
    const { rows } = mount(el, 100, 3);
    el.dispatchEvent(new Event("scroll"));
    await Promise.resolve();
    expect(rows.value[0].index).toBe(7);
    expect(rows.value.at(-1)!.index).toBe(17);
  });
});
