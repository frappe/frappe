// The page frame: its header row teleports to the shell's target, and `scroll` picks who scrolls.
import { afterEach, describe, expect, it } from "vitest";
import {
  createApp,
  defineComponent,
  h,
  nextTick,
  ref,
  type Component,
} from "vue";
import { PageHeaderTarget } from "frappe-ui";

import PageFrame, { pageGutter } from "../PageFrame.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

/** A shell in miniature: the pinned target above the page, as `DesktopShell` lays it out. */
async function mount(page: Component) {
  const root = document.createElement("div");
  document.body.appendChild(root);

  const app = createApp(
    defineComponent({
      render: () => [
        h("div", { "data-testid": "target" }, [h(PageHeaderTarget)]),
        h("div", { "data-testid": "page" }, [h(page)]),
      ],
    })
  );
  app.mount(root);
  mounted.push(app);
  // The target registers on mount, and a deferred teleport moves on the tick after that.
  await nextTick();
  await nextTick();

  const target = root.querySelector<HTMLElement>('[data-testid="target"]')!;
  return {
    target,
    page: root.querySelector<HTMLElement>('[data-testid="page"]')!,
    /** The header row; the band block above it is a `header` too, so a bare query would find that. */
    row: () => target.querySelector<HTMLElement>("header:not([data-page-above])"),
    above: () => target.querySelector<HTMLElement>("[data-page-above]")!,
  };
}

describe("the header row", () => {
  it("teleports the title into the shell's target, out of the page's own tree", async () => {
    const { row, page } = await mount(() =>
      h(PageFrame, { title: "Lead" }, () => "rows")
    );

    const header = row();
    expect(header?.textContent).toContain("Lead");
    expect(page.querySelector("header")).toBeNull();
    expect(page.textContent).toContain("rows");
  });

  it("renders the header slot in place of the title", async () => {
    const { row } = await mount(() =>
      h(
        PageFrame,
        { title: "Unused" },
        { header: () => h("h1", "Leads, mine") }
      )
    );

    const header = row()!;
    expect(header.textContent).toContain("Leads, mine");
    expect(header.textContent).not.toContain("Unused");
  });

  it("draws the row for a header slot that appears after mount", async () => {
    const headed = ref(false);
    const { row } = await mount(() =>
      h(PageFrame, null, headed.value ? { header: () => h("h1", "Late") } : {})
    );
    expect(row()).toBeNull();

    headed.value = true;
    await nextTick();
    await nextTick();
    expect(row()?.textContent).toContain("Late");
  });

  it("draws no row on a page with nothing for it, and nothing above it", async () => {
    const { target, row, page } = await mount(() =>
      h(PageFrame, null, () => "body")
    );

    expect(row()).toBeNull();
    expect(target.textContent).toBe("");
    expect(page.textContent).toContain("body");
  });
});

describe("the band block above the row", () => {
  it("sits in the target before the row, with the page gutter variable on it", async () => {
    const { row, above } = await mount(() =>
      h(PageFrame, { title: "Lead" }, { aboveHeader: () => h("p", "strip") })
    );

    const block = above();
    expect(block.textContent).toBe("strip");
    expect(block.parentElement!.firstElementChild).toBe(block);
    expect(block.nextElementSibling).toBe(row());
    expect(block.className).toContain("--page-gutter");
  });

  it("keeps a band supplied after mount above a row that was there first", async () => {
    const banded = ref(false);
    const { row, above } = await mount(() =>
      h(
        PageFrame,
        { title: "Lead" },
        banded.value ? { aboveHeader: () => h("p", "late strip") } : {}
      )
    );
    expect(above().textContent).toBe("");

    banded.value = true;
    await nextTick();
    await nextTick();
    expect(above().textContent).toBe("late strip");
    expect(above().parentElement!.firstElementChild).toBe(above());
    expect(above().nextElementSibling).toBe(row());
  });
});

describe("the scroll prop", () => {
  it("scrolls the body itself by default, with the gutter on the viewport", async () => {
    const { page } = await mount(() =>
      h(PageFrame, { title: "Home" }, () => "body")
    );

    const viewport = page.querySelector<HTMLElement>(
      '[data-slot="scroll-area-viewport"]'
    );
    expect(viewport).not.toBeNull();
    for (const cls of pageGutter.split(" "))
      expect(viewport!.classList.contains(cls)).toBe(true);
  });

  it("hands the scroll to the page with scroll=false, and applies no gutter", async () => {
    const { page } = await mount(() =>
      h(PageFrame, { title: "Lead", scroll: false }, () => h("p", "body"))
    );

    expect(page.querySelector('[data-slot="scroll-area"]')).toBeNull();
    // The band block's anchor comes first in the page's tree; the pane is the first element with a class.
    const pane = page.querySelector<HTMLElement>("div")!;
    expect(pane.className).toContain("overflow-hidden");
    expect(pane.className).not.toContain("px-");
  });
});
