// A band's wrapper: one element per band, the gutter unless opted out, and `page` beside its props.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h } from "vue";
import FrameBands from "../FrameBands.vue";
import { pageGutter } from "@/shell/PageFrame.vue";

const Band = defineComponent({
  props: { page: Object, tone: String },
  setup: (props) => () => h("p", `${props.tone}:${props.page?.docname}`),
});

const page = { doctype: "CRM Deal", docname: "D-1" } as any;
const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

function mount(bands: any[]) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({ render: () => h(FrameBands, { bands, page }) });
  app.mount(root);
  mounted.push(app);
  return root;
}

describe("FrameBands", () => {
  it("draws one wrapper per band, with the page's props reaching the component", () => {
    const root = mount([
      { name: "banner", component: Band, props: { tone: "warning" } },
      { name: "footer", component: Band, props: { tone: "note" } },
    ]);
    const wrappers = root.querySelectorAll("[data-frame-band]");
    expect(wrappers.length).toBe(2);
    expect(wrappers[0].getAttribute("data-frame-band")).toBe("banner");
    expect(wrappers[0].textContent).toBe("warning:D-1");
    expect(wrappers[1].textContent).toBe("note:D-1");
  });

  it("carries the page gutter by default and drops it on gutter: false", () => {
    const root = mount([
      { name: "banner", component: Band },
      { name: "strip", component: Band, gutter: false },
    ]);
    const [banner, strip] = root.querySelectorAll<HTMLElement>("[data-frame-band]");
    expect(banner.classList.contains(pageGutter)).toBe(true);
    expect(strip.classList.contains(pageGutter)).toBe(false);
    expect(strip.className).toBe("");
  });

  it("draws nothing for no bands", () => {
    expect(mount([]).querySelector("[data-frame-band]")).toBeNull();
  });
});
