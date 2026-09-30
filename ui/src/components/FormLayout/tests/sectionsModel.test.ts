import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App, Ref } from "vue";
import FormLayout from "../FormLayout.vue";
import type { FormLayoutSchema, Section } from "../types";

// The reader keeps their open and closed sections when the form is rebuilt.
// `Tabs` is stubbed because reka-ui paints nothing under happy-dom.
vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  Tabs: defineComponent({
    props: { tabs: { type: Array, required: true }, modelValue: [String, Number] },
    emits: ["update:modelValue"],
    setup(props, { emit, slots }) {
      return () => {
        const tabs = props.tabs as any[];
        return h("div", { "data-active": String(props.modelValue) }, [
          ...tabs.map((tab) =>
            h("button", {
              "data-tab": tab.identity,
              onClick: () => emit("update:modelValue", tab.value),
            })
          ),
          slots["tab-panel"]?.({
            tab: tabs.find((tab) => tab.value === props.modelValue) ?? tabs[0],
          }),
        ]);
      };
    },
  }),
}));

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

const section = (fields: Partial<Section>): Section => ({ columns: [], ...fields });

/** Two tabs that both carry a `notes` section; the first also has a closed and an unnamed one. */
const LAYOUT: FormLayoutSchema = [
  {
    name: "details",
    label: "Details",
    sections: [
      section({ name: "notes", label: "Notes" }),
      section({ name: "address", label: "Address", opened: false }),
      section({ label: "Unnamed" }),
    ],
  },
  {
    name: "more",
    label: "More",
    sections: [section({ name: "notes", label: "Notes" })],
  },
];

/** Mount the form; with `sections` given, a host owns that model as it owns `tab`. */
function mount(sections?: Ref<Record<string, boolean>>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const shown = ref(true);
  const emitted: Record<string, boolean>[] = [];
  const doc = ref<Record<string, any>>({});
  const tab = ref("");
  const onUpdate = (value: Record<string, boolean>) => {
    emitted.push(value);
    sections!.value = value;
  };
  app = createApp(
    defineComponent({
      setup() {
        return () =>
          shown.value
            ? h(FormLayout, {
                layout: LAYOUT,
                doc: doc.value,
                "onUpdate:doc": (value: any) => (doc.value = value),
                tab: tab.value,
                "onUpdate:tab": (identity: string) => (tab.value = identity),
                ...(sections
                  ? { sections: sections.value, "onUpdate:sections": onUpdate }
                  : {}),
              })
            : h("div");
      },
    })
  );
  app.mount(host);

  const sectionEl = (label: string) =>
    [...host!.querySelectorAll<HTMLElement>(".section")].find(
      (el) => el.querySelector(".section-header")?.textContent?.trim() === label
    )!;
  const header = (label: string) => sectionEl(label).querySelector<HTMLElement>(".section-header")!;
  const content = (label: string) => sectionEl(label).querySelector(".form-section-content")!;
  return {
    emitted,
    // reka-ui leaves `data-state` off an open content until the next frame; the header has it at once.
    state: (label: string) => header(label).getAttribute("data-state"),
    animated: (label: string) => content(label).classList.contains("is-animated"),
    toggle: async (label: string) => {
      header(label).click();
      await nextTick();
    },
    openTab: async (identity: string) => {
      host!.querySelector<HTMLElement>(`[data-tab="${identity}"]`)!.click();
      await nextTick();
    },
    /** What a save does: the panel is torn down and built again from scratch. */
    remount: async () => {
      shown.value = false;
      await nextTick();
      shown.value = true;
      await nextTick();
    },
  };
}

describe("sections with no host state", () => {
  it("start where the layout says: absent is open, false stays closed", () => {
    const form = mount();
    expect(form.state("Notes")).toBe("open");
    expect(form.state("Address")).toBe("closed");
  });

  it("toggle on a click on the header", async () => {
    const form = mount();
    await form.toggle("Notes");
    expect(form.state("Notes")).toBe("closed");
    await form.toggle("Address");
    expect(form.state("Address")).toBe("open");
  });
});

describe("sections bound to a host", () => {
  it("emit the new map keyed by tab and section name", async () => {
    const form = mount(ref({}));
    await form.toggle("Notes");
    expect(form.emitted.at(-1)).toEqual({ "details:notes": false });
    expect(form.state("Notes")).toBe("closed");
  });

  it("key an unnamed section by its index", async () => {
    const form = mount(ref({ "details:notes": false }));
    await form.toggle("Unnamed");
    expect(form.emitted.at(-1)).toEqual({ "details:notes": false, "details:2": false });
  });

  it("take the host's value over `section.opened`", () => {
    const form = mount(ref({ "details:notes": false, "details:address": true }));
    expect(form.state("Notes")).toBe("closed");
    expect(form.state("Address")).toBe("open");
  });

  it("come back the same after a rebuild, without a collapse animation", async () => {
    const form = mount(ref({}));
    await form.toggle("Notes");
    await form.toggle("Address");
    expect(form.animated("Notes")).toBe(true);

    await form.remount();
    expect(form.state("Notes")).toBe("closed");
    expect(form.state("Address")).toBe("open");
    expect(form.state("Unnamed")).toBe("open");
    expect(form.animated("Notes")).toBe(false);
    expect(form.animated("Address")).toBe(false);
  });

  it("keep one state per tab for the same section name", async () => {
    const sections = ref<Record<string, boolean>>({});
    const form = mount(sections);
    await form.toggle("Notes");

    await form.openTab("more");
    expect(form.state("Notes")).toBe("open");
    expect(sections.value).toEqual({ "details:notes": false });

    await form.toggle("Notes");
    await form.toggle("Notes");
    expect(sections.value).toEqual({ "details:notes": false, "more:notes": true });

    await form.openTab("details");
    expect(form.state("Notes")).toBe("closed");
  });
});
