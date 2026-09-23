// The strip over the tab bodies: a skeleton until the first replay, a body that stays mounted after its first visit, and its focus.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, reactive } from "vue";

const strips: unknown[] = [];

vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  Tabs: defineComponent({
    props: { modelValue: String, tabs: Array },
    emits: ["update:modelValue"],
    setup(props, { emit }) {
      return () => {
        strips.push(props.tabs);
        return h(
          "nav",
          (props.tabs as { value: string }[]).map((tab) =>
            h("button", { "data-tab": tab.value, onClick: () => emit("update:modelValue", tab.value) }),
          ),
        );
      };
    },
  }),
}));

import RecordTabs from "../RecordTabs.vue";
import type { ResolvedItem } from "@/recordPage/surface";
import type { TabItem } from "@/recordPage/types";
import { recordTabBuiltins, RecordTabsHost } from "../recordTabs";
import { Surface } from "@/recordPage/surface";
import { TAB_ITEM_KEYS } from "@/recordPage/types";

const Audit = defineComponent({
  props: { page: Object, limit: Number },
  setup: (props) => () => h("p", { "data-audit": "" }, `${props.page?.docname}:${props.limit}`),
});

const page = { doctype: "CRM Deal", docname: "D-1" } as any;
const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  strips.length = 0;
});

function entry(name: string, extra: Partial<TabItem> = {}, hidden = false): ResolvedItem<TabItem> {
  return { item: { name, label: name, ...extra }, source: "builtin", hidden };
}

async function mount(
  tabs: ResolvedItem<TabItem>[],
  active: string,
  ready = true,
  onSelect?: (name: string) => unknown,
  claimsFocus?: (name: string) => boolean,
) {
  const state = reactive({ tabs, active, ready, page, claimsFocus });
  const selected: string[] = [];
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({
    render: () =>
      h(
        RecordTabs,
        { ...state, onSelect: onSelect ?? ((name: string) => selected.push(name)) },
        { details: () => h("form", { "data-details": "" }, [h("input", { "data-field": "" })]) },
      ),
  });
  app.mount(root);
  apps.push(app);
  await nextTick();
  return { root, state, selected };
}

const FOUR = [entry("activity"), entry("emails"), entry("files"), entry("details")];

function body(root: HTMLElement, name: string) {
  return root.querySelector<HTMLElement>(`[data-record-tab="${name}"]`);
}

function viewport(root: HTMLElement, name: string) {
  return body(root, name)!.querySelector<HTMLElement>("[data-reka-scroll-area-viewport]")!;
}

function frame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

describe("before the first replay", () => {
  it("draws a skeleton and no body", async () => {
    const { root } = await mount(FOUR, "", false);

    expect(root.querySelectorAll("[data-record-tabs-skeleton] .fui-skeleton")).toHaveLength(4);
    expect(root.querySelector("nav")).toBeNull();
    expect(root.querySelector("[data-record-tab]")).toBeNull();
  });
});

describe("the strip", () => {
  it("draws the visible tabs, each with its icon on the left of its label", async () => {
    await mount([entry("activity", { icon: "lucide-activity" }), entry("emails", {}, true)], "activity");

    expect(strips.at(-1)).toEqual([{ value: "activity", label: "activity", iconLeft: "lucide-activity" }]);
  });

  it("hands the reader's pick up, and moves nothing itself", async () => {
    const { root, selected } = await mount(FOUR, "activity");

    root.querySelector<HTMLElement>('[data-tab="files"]')!.click();
    await nextTick();

    expect(selected).toEqual(["files"]);
    expect(body(root, "files")).toBeNull();
  });

  it("moves the reader through the host's own method, passed bare as the page passes it", async () => {
    const route = reactive({ query: {} as Record<string, any>, hash: "" });
    const router = { replace: vi.fn(async (to: any) => void (route.query = to.query)) } as any;
    const tabs = new Surface<TabItem>({ surface: "tabs", keys: TAB_ITEM_KEYS });
    tabs.provideBuiltins(recordTabBuiltins);
    const host = new RecordTabsHost(route as any, router, () => tabs);
    const { root } = await mount(FOUR, "activity", true, host.activate);

    root.querySelector<HTMLElement>('[data-tab="files"]')!.click();
    await nextTick();

    expect(route.query.tab).toBe("files");
    expect(host.shown()).toBe("files");
  });

  it("draws nothing when no tab is visible", async () => {
    const { root } = await mount([entry("activity", {}, true)], "");

    expect(root.querySelector("nav")).toBeNull();
    expect(root.querySelector("[data-record-tab]")).toBeNull();
  });
});

describe("the bodies", () => {
  it("mounts only the shown tab on a cold load", async () => {
    const { root } = await mount(FOUR, "activity");

    expect(root.querySelectorAll("[data-record-tab]")).toHaveLength(1);
    expect(body(root, "activity")).not.toBeNull();
  });

  it("keeps a visited body mounted and hidden after a switch", async () => {
    const { root, state } = await mount(FOUR, "details");
    const form = root.querySelector("[data-details]");

    state.active = "activity";
    await nextTick();

    expect(body(root, "details")!.style.display).toBe("none");
    expect(root.querySelector("[data-details]")).toBe(form);
    expect(body(root, "activity")!.style.display).toBe("");
  });

  it("scrolls each body in its own viewport, which keeps its place across a switch", async () => {
    const { root, state } = await mount(FOUR, "details");
    const details = viewport(root, "details");
    details.scrollTop = 300;

    state.active = "activity";
    await nextTick();
    viewport(root, "activity").scrollTop = 40;
    state.active = "details";
    await nextTick();

    expect(viewport(root, "details")).toBe(details);
    expect(details.scrollTop).toBe(300);
    expect(viewport(root, "activity").scrollTop).toBe(40);
  });

  it("keeps the body of a tab a script hides", async () => {
    const { root, state } = await mount(FOUR, "files");

    state.tabs = [entry("activity"), entry("emails"), entry("files", {}, true), entry("details")];
    state.active = "activity";
    await nextTick();

    expect(body(root, "files")).not.toBeNull();
    expect(body(root, "files")!.style.display).toBe("none");
  });

  it("draws Details from the host's slot and an empty state for a tab with no component", async () => {
    const { root, state } = await mount(FOUR, "details");

    expect(body(root, "details")!.querySelector("[data-details]")).not.toBeNull();
    state.active = "emails";
    await nextTick();
    expect(body(root, "emails")!.textContent).toContain("Nothing here yet.");
  });

  it("gives a scripted tab its props and the page", async () => {
    const audit = entry("audit", { component: Audit, props: { limit: 20 } });
    const { root } = await mount([...FOUR, audit], "audit");

    expect(root.querySelector("[data-audit]")!.textContent).toBe("D-1:20");
  });

  it("draws a script's component for a built-in name it replaced", async () => {
    const { root } = await mount([entry("details", { component: Audit })], "details");

    expect(root.querySelector("[data-audit]")).not.toBeNull();
    expect(root.querySelector("[data-details]")).toBeNull();
  });

  it("starts fresh on a new page: no body of the last page stays mounted", async () => {
    const { root, state } = await mount(FOUR, "details");
    state.active = "activity";
    await nextTick();

    state.page = { doctype: "CRM Deal", docname: "D-2" } as any;
    await nextTick();

    expect(body(root, "details")).toBeNull();
    expect(body(root, "activity")).not.toBeNull();
  });
});

describe("focus", () => {
  it("returns to the field the reader left when a script brings its tab back", async () => {
    const { root, state } = await mount(FOUR, "details");
    const input = root.querySelector<HTMLInputElement>("[data-field]")!;
    input.focus();

    state.active = "activity";
    await nextTick();
    input.blur();
    state.active = "details";
    await nextTick();
    await frame();

    expect(document.activeElement).toBe(input);
  });

  it("stays on the strip when the reader moves tabs with the keyboard", async () => {
    const { root, state } = await mount(FOUR, "details");
    const input = root.querySelector<HTMLInputElement>("[data-field]")!;
    input.focus();
    state.active = "activity";
    await nextTick();
    const trigger = root.querySelector<HTMLElement>('[data-tab="details"]')!;
    trigger.focus();

    state.active = "details";
    await nextTick();
    await frame();

    expect(document.activeElement).toBe(trigger);
  });

  it("returns to the field after a click on the strip", async () => {
    const { root, state } = await mount(FOUR, "details");
    const input = root.querySelector<HTMLInputElement>("[data-field]")!;
    input.focus();
    state.active = "activity";
    await nextTick();
    const trigger = root.querySelector<HTMLElement>('[data-tab="details"]')!;
    trigger.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    trigger.focus();

    state.active = "details";
    await nextTick();
    await frame();

    expect(document.activeElement).toBe(input);
  });

  it("leaves focus on an input outside the column when a script moves the reader", async () => {
    const { root, state } = await mount(FOUR, "details");
    root.querySelector<HTMLInputElement>("[data-field]")!.focus();
    state.active = "activity";
    await nextTick();
    const outside = document.createElement("input");
    document.body.appendChild(outside);
    outside.focus();

    state.active = "details";
    await nextTick();
    await frame();

    expect(document.activeElement).toBe(outside);
  });

  it("leaves focus alone when the page placed it on the move", async () => {
    const claimed: string[] = [];
    const claimsFocus = (name: string) => (claimed.push(name), true);
    const { root, state } = await mount(FOUR, "details", true, undefined, claimsFocus);
    const input = root.querySelector<HTMLInputElement>("[data-field]")!;
    input.focus();
    state.active = "activity";
    await nextTick();
    input.blur();

    state.active = "details";
    await nextTick();
    await frame();

    expect(claimed).toEqual(["activity", "details"]);
    expect(document.activeElement).toBe(document.body);
  });
});
