import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App, Ref } from "vue";
import FormLayout from "../FormLayout.vue";
import type { FormLayoutSchema } from "../types";

/**
 * The tab strip's promise, at the DOM: *the reader keeps their place*.
 *
 * Two failures are asserted against, and a fix for one that isn't a fix for the
 * other is not a fix — an index survives neither, and an identity held inside
 * the component survives only the second:
 *
 *  1. the form is destroyed and rebuilt (what a save does to it), and
 *  2. a `depends_on` tab appears or disappears beside the reader.
 *
 * frappe-ui's `Tabs` is stubbed because reka-ui paints nothing under happy-dom.
 * The stub is deliberately faithful about the one thing under test: it speaks
 * only `modelValue` *indices*, exactly as the real wrapper does, so these tests
 * exercise the identity/index translation rather than assuming it away.
 */
vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  Tabs: defineComponent({
    props: { tabs: { type: Array, required: true }, modelValue: Number },
    emits: ["update:modelValue"],
    setup(props, { emit, slots }) {
      return () =>
        h("div", { "data-active-index": String(props.modelValue) }, [
          ...(props.tabs as any[]).map((tab, index) =>
            h("button", {
              "data-tab": tab.identity,
              "data-label": tab.label,
              onClick: () => emit("update:modelValue", index),
            })
          ),
          slots["tab-panel"]?.({
            tab: (props.tabs as any[])[props.modelValue ?? 0],
          }),
        ]);
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

/** Three tabs, the middle one conditional on `doc.extra`. */
const LAYOUT: FormLayoutSchema = [
  { name: "organization", label: "Organization", sections: [] },
  {
    name: "products",
    label: "Products",
    dependsOn: "eval:doc.extra",
    sections: [],
  },
  { name: "contacts", label: "Contacts", sections: [] },
];

/**
 * Mount the form under a host that owns the `tab` model, as `RecordTabs` does —
 * the arrangement the whole design rests on, since the form itself does not
 * survive a save.
 */
function mount(
  doc: Ref<Record<string, any>>,
  tab: Ref<string>,
  layout: Ref<FormLayoutSchema> = ref(LAYOUT)
) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const shown = ref(true);
  const announced: string[] = [];
  app = createApp(
    defineComponent({
      setup() {
        return () =>
          shown.value
            ? h(FormLayout, {
                layout: layout.value,
                doc: doc.value,
                "onUpdate:doc": (value: any) => (doc.value = value),
                tab: tab.value,
                "onUpdate:tab": (identity: string) => (tab.value = identity),
                "onUpdate:activeTab": (identity: string) =>
                  announced.push(identity),
              })
            : h("div");
      },
    })
  );
  app.mount(host);

  const triggers = () => [...host!.querySelectorAll("[data-tab]")];
  return {
    labels: () => triggers().map((el) => el.getAttribute("data-label")),
    /** Every `update:activeTab` since mount, in order. */
    announced: () => announced,
    identities: () => triggers().map((el) => el.getAttribute("data-tab")),
    activeIdentity: () => {
      const index = Number(
        host!
          .querySelector("[data-active-index]")!
          .getAttribute("data-active-index")
      );
      return triggers()[index]?.getAttribute("data-tab");
    },
    click: async (identity: string) => {
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

describe("the reader keeps their place", () => {
  it("starts on the first visible tab", () => {
    const strip = mount(ref({ extra: 1 }), ref(""));
    expect(strip.activeIdentity()).toBe("organization");
  });

  it("survives the form being destroyed and rebuilt", async () => {
    const strip = mount(ref({ extra: 1 }), ref(""));

    await strip.click("contacts");
    expect(strip.activeIdentity()).toBe("contacts");

    await strip.remount();
    expect(strip.activeIdentity()).toBe("contacts");
  });

  it("does not move the reader when a tab appears beside them", async () => {
    const doc = ref<Record<string, any>>({ extra: 0 });
    const strip = mount(doc, ref(""));

    await strip.click("contacts");
    doc.value.extra = 1;
    await nextTick();

    expect(strip.identities()).toEqual(["organization", "products", "contacts"]);
    expect(strip.activeIdentity()).toBe("contacts");
  });

  it("falls back to the first tab when the reader's tab disappears", async () => {
    const doc = ref<Record<string, any>>({ extra: 1 });
    const strip = mount(doc, ref(""));

    await strip.click("products");
    doc.value.extra = 0;
    await nextTick();

    expect(strip.identities()).toEqual(["organization", "contacts"]);
    expect(strip.activeIdentity()).toBe("organization");
  });

  it("returns the reader to their tab when it comes back", async () => {
    const doc = ref<Record<string, any>>({ extra: 1 });
    const strip = mount(doc, ref(""));

    await strip.click("products");
    doc.value.extra = 0;
    await nextTick();
    doc.value.extra = 1;
    await nextTick();

    // The miss never overwrote the intent, so remembering it costs nothing.
    expect(strip.activeIdentity()).toBe("products");
  });

  it("addresses by identity, not position, when the set shifts under it", async () => {
    // The old index bug in one assertion: `contacts` is index 2, then index 1.
    const doc = ref<Record<string, any>>({ extra: 1 });
    const strip = mount(doc, ref(""));

    await strip.click("contacts");
    doc.value.extra = 0;
    await nextTick();

    expect(strip.activeIdentity()).toBe("contacts");
  });

  it("keeps unlabelled, unnamed tabs apart when one of them hides", async () => {
    // The weakest layout there is: nothing to key on but position, and the
    // strip relabels every one of them "Details" for the reader. Identity is
    // resolved over the whole layout and before that relabelling, so hiding the
    // second tab must not renumber the third onto the second's identity.
    host = document.createElement("div");
    document.body.appendChild(host);
    const doc = ref<Record<string, any>>({ extra: 1 });
    app = createApp(
      defineComponent({
        setup() {
          return () =>
            h(FormLayout, {
              layout: [
                { sections: [] },
                { dependsOn: "eval:doc.extra", sections: [] },
                { sections: [] },
              ] as FormLayoutSchema,
              doc: doc.value,
              "onUpdate:doc": (value: any) => (doc.value = value),
            });
        },
      })
    );
    app.mount(host);

    const identities = () =>
      [...host!.querySelectorAll("[data-tab]")].map((el) =>
        el.getAttribute("data-tab")
      );
    const activeIdentity = () =>
      identities()[
        Number(
          host!
            .querySelector("[data-active-index]")!
            .getAttribute("data-active-index")
        )
      ];

    expect(identities()).toEqual(["tab-1", "tab-2", "tab-3"]);
    host.querySelector<HTMLElement>('[data-tab="tab-3"]')!.click();
    await nextTick();
    expect(activeIdentity()).toBe("tab-3");

    doc.value.extra = 0;
    await nextTick();
    expect(identities()).toEqual(["tab-1", "tab-3"]);
    expect(activeIdentity()).toBe("tab-3");
  });

  it("leaves the intent alone when handed an index naming no tab", async () => {
    // The wrapper cannot reach this today — every index it is given was just
    // derived from the list it rendered — but the model may be a host's, and
    // blanking someone else's state on a stray emit is not this component's to
    // do. Asserted because it is exactly what the first draft got wrong.
    const tab = ref("");
    const strip = mount(ref({ extra: 1 }), tab);

    await strip.click("contacts");
    expect(tab.value).toBe("contacts");

    const wrapper = host!.querySelector("[data-active-index]")!;
    // @ts-expect-error reaching the stub's emit through the rendered vnode
    wrapper.__vnode.component.emit("update:modelValue", 99);
    await nextTick();

    expect(tab.value).toBe("contacts");
  });

  it("announces the resolved identity, on mount and on every move", async () => {
    const doc = ref<Record<string, any>>({ extra: 1 });
    const strip = mount(doc, ref(""));

    // On mount, so a host that has just been rebuilt is told where the reader
    // landed without having to re-derive the resolution itself.
    expect(strip.announced()).toEqual(["organization"]);

    await strip.click("products");
    doc.value.extra = 0;
    await nextTick();

    // The `depends_on` miss moved the reader without touching their intent —
    // the case the model alone cannot report.
    expect(strip.announced()).toEqual([
      "organization",
      "products",
      "organization",
    ]);
  });

  it("announces the same identity after a rebuild, so nothing reads as a move", async () => {
    const strip = mount(ref({ extra: 1 }), ref(""));

    await strip.click("contacts");
    await strip.remount();

    expect(strip.announced()).toEqual(["organization", "contacts", "contacts"]);
  });

  it("works standalone, with no host holding the model", async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp(
      defineComponent({
        setup() {
          const doc = ref({ extra: 1 });
          return () =>
            h(FormLayout, {
              layout: LAYOUT,
              doc: doc.value,
              "onUpdate:doc": (value: any) => (doc.value = value),
            });
        },
      })
    );
    app.mount(host);

    host.querySelector<HTMLElement>('[data-tab="contacts"]')!.click();
    await nextTick();
    expect(
      host.querySelector("[data-active-index]")!.getAttribute("data-active-index")
    ).toBe("2");
  });
});

/**
 * The per-render override: plain data on the tab, applied where the strip is
 * drawn. `FormLayout` knows nothing about who wrote it — on the Record page it
 * is a Page Script's `page.formTabs`, which is what makes these two rules load
 * bearing rather than incidental.
 */
describe("a per-render tab override", () => {
  const overridden = (override: Record<string, any>) =>
    ref(
      LAYOUT.map((tab) =>
        tab.name === "products" ? { ...tab, override } : tab
      ) as FormLayoutSchema
    );

  it("hides a tab the layout shows", async () => {
    const strip = mount(ref({ extra: 1 }), ref(""), overridden({ hidden: true }));

    expect(strip.identities()).toEqual(["organization", "contacts"]);
  });

  it("shows a tab its `depends_on` hides", async () => {
    // The whole reason the override is applied here and not folded in as a
    // static `hidden` at build time: `resolveLayout` ORs that with the
    // expression, so a `show()` written that way would be silently inert.
    const strip = mount(
      ref({ extra: 0 }),
      ref(""),
      overridden({ hidden: false })
    );

    expect(strip.identities()).toEqual([
      "organization",
      "products",
      "contacts",
    ]);
  });

  it("relabels a tab without moving its identity", async () => {
    // An unnamed tab's identity is its label slugified, so a relabelling that
    // ran before identity would rename the very address the override was
    // written against.
    const layout = ref([
      { label: "Organization", sections: [] },
      { label: "Products", sections: [] },
    ] as FormLayoutSchema);
    const strip = mount(ref({}), ref(""), layout);
    expect(strip.identities()).toEqual(["organization", "products"]);

    layout.value = [
      layout.value[0],
      { ...layout.value[1], override: { label: "Items" } },
    ];
    await nextTick();

    expect(strip.identities()).toEqual(["organization", "products"]);
    expect(strip.labels()).toEqual(["Organization", "Items"]);
  });

  it("brings the reader back when the tab they were on is shown again", async () => {
    const layout = overridden({ hidden: false });
    const strip = mount(ref({ extra: 0 }), ref(""), layout);

    await strip.click("products");
    layout.value = LAYOUT;
    await nextTick();
    expect(strip.activeIdentity()).toBe("organization");

    layout.value = overridden({ hidden: false }).value;
    await nextTick();
    expect(strip.activeIdentity()).toBe("products");
  });
});
