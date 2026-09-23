// The strip over the tab bodies: a skeleton until the first replay, and a body that stays mounted after its first visit.
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

async function mount(tabs: ResolvedItem<TabItem>[], active: string, ready = true) {
  const state = reactive({ tabs, active, ready });
  const selected: string[] = [];
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({
    render: () =>
      h(
        RecordTabs,
        { ...state, page, onSelect: (name: string) => selected.push(name) },
        { details: () => h("form", { "data-details": "" }) },
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

describe("before the first replay", () => {
  it("draws a skeleton and no body", async () => {
    const { root } = await mount(FOUR, "", false);

    expect(root.querySelector("[data-record-tabs-skeleton]")).not.toBeNull();
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

  it("keeps the body of a tab a script hides", async () => {
    const { root, state } = await mount(FOUR, "files");

    state.tabs = [entry("activity"), entry("emails"), entry("files", {}, true), entry("details")];
    state.active = "activity";
    await nextTick();

    expect(body(root, "files")).not.toBeNull();
    expect(body(root, "files")!.style.display).toBe("none");
  });

  it("draws Details from the host's slot and an empty state for the other built-ins", async () => {
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
});
