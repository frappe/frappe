// The customize dialog and the list operations under it. Mounted with Vue's own
// `createApp`: this package has no `@vue/test-utils`.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type VNode } from "vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ runMethod: fake.runMethod }));

// The real barrel drags the icon plugins in. `Button` is stubbed as the element it renders,
// keeping `aria-label` and `@click`, which is all these tests reach for.
vi.mock("frappe-ui", () => ({
  // A render function, not a `template`: vitest resolves `vue` to the runtime-only build,
  // which has no compiler, so a string template silently renders nothing at all.
  Button: {
    props: ["label", "icon", "variant", "loading", "disabled"],
    emits: ["click"],
    setup:
      (
        props: { label?: string; loading?: boolean; disabled?: boolean },
        { emit }: { emit: (event: string) => void }
      ) =>
      () =>
      h(
        "button",
        {
          onClick: () => emit("click"),
          disabled: props.disabled,
          "data-loading": props.loading ? "true" : undefined,
        },
        props.label ?? ""
      ),
  },
  Skeleton: { setup: () => () => h("div", { class: "fui-skeleton" }) },
  // Rendered in place, not portaled, and only while open: what the shell's hash decides.
  Dialog: {
    props: ["modelValue", "title", "size"],
    setup:
      (
        props: { modelValue: boolean; title?: string },
        { slots }: { slots: { default?: () => VNode[]; actions?: () => VNode[] } }
      ) =>
      () =>
        props.modelValue
          ? h("div", { role: "dialog" }, [
              h("h3", props.title),
              ...(slots.default?.() ?? []),
              ...(slots.actions?.() ?? []),
            ])
          : null,
  },
}));

import CustomizeSidebarDialog, { type CustomizeTarget } from "../CustomizeSidebarDialog.vue";
import { dropOn, move, saveArrangement, type ArrangedItem } from "@/arrangement";

const runMethod = fake.runMethod;

/** Let the mount's own `await` chain settle, then let Vue re-render off it. */
async function flush() {
  await Promise.resolve();
  await Promise.resolve();
  await nextTick();
}

function item(key: string, extra: Partial<ArrangedItem> = {}): ArrangedItem {
  return { key, item_type: "DocType", link_to: key, ...extra };
}

function keys(items: ArrangedItem[]): string[] {
  return items.map((entry) => entry.key);
}

describe("moving a row", () => {
  const flat = [item("a"), item("b"), item("c")];

  it("swaps a row with the one after it", () => {
    expect(keys(move(flat, "a", 1))).toEqual(["b", "a", "c"]);
  });

  it("swaps a row with the one before it", () => {
    expect(keys(move(flat, "c", -1))).toEqual(["a", "c", "b"]);
  });

  it("does not wrap at either end", () => {
    expect(keys(move(flat, "a", -1))).toEqual(["a", "b", "c"]);
    expect(keys(move(flat, "c", 1))).toEqual(["a", "b", "c"]);
  });

  it("steps over a row under a different parent", () => {
    // `x` is the last child of the section, so "down" for `b` is `c` -- not `x`, which is
    // between them in the flat list but is not its sibling.
    const nested = [item("a"), item("s"), item("x", { parent_key: "s" }), item("b"), item("c")];

    expect(keys(move(nested, "b", 1))).toEqual(["a", "s", "x", "c", "b"]);
  });

  it("does not move a row out of its section", () => {
    const nested = [item("s"), item("x", { parent_key: "s" }), item("b")];

    expect(keys(move(nested, "x", -1))).toEqual(["s", "x", "b"]);
    expect(keys(move(nested, "x", 1))).toEqual(["s", "x", "b"]);
  });

  it("takes a section's children with it", () => {
    // The list is flat and the tree is `parent_key`, so swapping two headers alone would leave
    // each section's children sitting under the other one on screen.
    const sections = [
      item("s1"),
      item("a", { parent_key: "s1" }),
      item("s2"),
      item("b", { parent_key: "s2" }),
    ];

    expect(keys(move(sections, "s1", 1))).toEqual(["s2", "b", "s1", "a"]);
  });

  it("leaves a list it cannot find the row in alone", () => {
    expect(move(flat, "nope", 1)).toBe(flat);
  });
});

describe("dropping a row", () => {
  const flat = [item("a"), item("b"), item("c")];

  it("puts a row where the one it was dropped on sits", () => {
    expect(keys(dropOn(flat, "a", "c"))).toEqual(["b", "c", "a"]);
    expect(keys(dropOn(flat, "c", "a"))).toEqual(["c", "a", "b"]);
  });

  it("refuses a drop onto a row under a different parent", () => {
    // Two edits at once -- a reparent and a reorder -- and a drag that silently did the first
    // is how a whole section ends up somewhere nobody put it.
    const nested = [item("s"), item("x", { parent_key: "s" }), item("b")];

    expect(dropOn(nested, "b", "x")).toBe(nested);
  });

  it("refuses a drop on itself", () => {
    expect(dropOn(flat, "a", "a")).toBe(flat);
  });

  it("carries a dragged section's children too", () => {
    const sections = [
      item("s1"),
      item("a", { parent_key: "s1" }),
      item("s2"),
      item("b", { parent_key: "s2" }),
    ];

    expect(keys(dropOn(sections, "s2", "s1"))).toEqual(["s2", "b", "s1", "a"]);
  });
});

describe("the endpoint client", () => {
  beforeEach(() => runMethod.mockReset());

  it("sends the whole ordered list and the address it belongs to", async () => {
    runMethod.mockResolvedValue({ data: { rail: [], sidebars: {} } });
    const items = [item("b"), item("a")];

    await saveArrangement({ container: "Sidebar", address: "module_def_core" }, items);

    expect(runMethod).toHaveBeenCalledWith("frappe.shell.arrangement.save_arrangement", {
      container: "Sidebar",
      address: "module_def_core",
      scope: "user",
      items,
    });
  });

  it("defaults to a person's own layer, and never names a user", async () => {
    runMethod.mockResolvedValue({ data: { rail: [], sidebars: {} } });

    await saveArrangement({ container: "Rail", address: "frappe" }, []);

    const [, args] = runMethod.mock.calls[0];
    expect(args.scope).toBe("user");
    expect(args).not.toHaveProperty("user");
  });
});

async function editor(rows: ArrangedItem[]) {
  runMethod.mockReset();
  runMethod.mockResolvedValue({ data: rows });

  const host = document.createElement("div");
  document.body.appendChild(host);
  const saved: unknown[] = [];
  const app = createApp({
    render: () =>
      h(CustomizeSidebarDialog, {
        target: { container: "Rail", address: "frappe", title: "Customize sidebar" },
        onSaved: (navigation: unknown) => saved.push(navigation),
      }),
  });
  app.mount(host);
  await flush();

  return {
    host,
    saved,
    rowKeys: () =>
      [...host.querySelectorAll("[data-key]")].map((row) => row.getAttribute("data-key")),
    click: async (label: string) => {
      const target =
        host.querySelector<HTMLElement>(`[aria-label="${label}"]`) ??
        [...host.querySelectorAll("button")].find((button) => button.textContent === label);
      target!.click();
      await flush();
    },
    type: async (label: string, value: string) => {
      const input = host.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!;
      input.value = value;
      input.dispatchEvent(new Event("input"));
      await flush();
    },
    sent: () => runMethod.mock.calls.at(-1)![1].items as ArrangedItem[],
  };
}


function button(host: HTMLElement, label: string): HTMLButtonElement {
  return [...host.querySelectorAll("button")].find((node) => node.textContent === label)!;
}

function rowKeys(host: HTMLElement): (string | null)[] {
  return [...host.querySelectorAll("[data-key]")].map((row) => row.getAttribute("data-key"));
}

/** A live host whose target is a ref; every fetch after the first waits in `resolvers`, in order. */
async function switching(first: ArrangedItem[]) {
  runMethod.mockReset();
  const resolvers: ((rows: ArrangedItem[]) => void)[] = [];
  runMethod.mockResolvedValueOnce({ data: first }).mockImplementation(
    () => new Promise((resolve) => resolvers.push((rows) => resolve({ data: rows })))
  );

  const target = ref<CustomizeTarget | null>({
    container: "Rail",
    address: "frappe",
    title: "Customize sidebar",
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  createApp({ render: () => h(CustomizeSidebarDialog, { target: target.value }) }).mount(host);
  await flush();

  return { host, target, resolvers };
}

describe("the dialog", () => {
  it("drops the old list the moment the target changes, and shows the new one when it lands", async () => {
    const { host, target, resolvers } = await switching([item("rail-row")]);
    expect(rowKeys(host)).toEqual(["rail-row"]);

    target.value = { container: "Sidebar", address: "sales", title: "Customize this sidebar" };
    await flush();
    expect(rowKeys(host)).toEqual([]);

    resolvers[0]([item("sidebar-row")]);
    await flush();
    expect(rowKeys(host)).toEqual(["sidebar-row"]);
  });

  it("keeps Save held while a new target loads, even when the old target's save lands", async () => {
    const { host, target, resolvers } = await switching([item("rail-row")]);
    button(host, "Save").click();
    await flush();

    target.value = { container: "Sidebar", address: "sales", title: "Customize this sidebar" };
    await flush();
    resolvers[0]({ rail: [], sidebars: {} } as unknown as ArrangedItem[]);
    await flush();

    const save = button(host, "Save");
    expect(save.disabled).toBe(true);
    expect(save.getAttribute("data-loading")).toBeNull();

    resolvers[1]([item("sidebar-row")]);
    await flush();
    expect(save.disabled).toBe(false);
  });

  it("draws skeleton rows while the list loads, and the real rows once it lands", async () => {
    const { host, target, resolvers } = await switching([item("rail-row")]);
    target.value = { container: "Sidebar", address: "sales", title: "Customize this sidebar" };
    await flush();

    expect(host.querySelectorAll("[data-customize-skeleton] li")).toHaveLength(5);
    expect(host.querySelectorAll("[data-customize-skeleton] .fui-skeleton")).toHaveLength(20);
    expect(host.querySelector("[data-testid='customize']")).toBeNull();

    resolvers[0]([item("sidebar-row")]);
    await flush();
    expect(host.querySelector("[data-customize-skeleton]")).toBeNull();
    expect(rowKeys(host)).toEqual(["sidebar-row"]);
  });

  it("does not spin Reset or Save during the load, only holds them", async () => {
    const { host, target } = await switching([]);
    target.value = { container: "Sidebar", address: "sales", title: "Customize this sidebar" };
    await flush();

    for (const label of ["Reset", "Save"]) {
      expect(button(host, label).getAttribute("data-loading")).toBeNull();
      expect(button(host, label).disabled).toBe(true);
    }
  });

  it("spins Reset through its own reload, over the rows rather than a skeleton", async () => {
    const { host, resolvers } = await switching([item("a")]);
    button(host, "Reset").click();
    await flush();
    expect(button(host, "Reset").getAttribute("data-loading")).toBe("true");

    resolvers[0]({ rail: [], sidebars: {} } as unknown as ArrangedItem[]);
    await flush();
    expect(button(host, "Reset").getAttribute("data-loading")).toBe("true");
    expect(host.querySelector("[data-customize-skeleton]")).toBeNull();
    expect(rowKeys(host)).toEqual(["a"]);

    resolvers[1]([item("b")]);
    await flush();
    await flush();
    expect(button(host, "Reset").getAttribute("data-loading")).toBeNull();
    expect(rowKeys(host)).toEqual(["b"]);
  });

  it("ignores a fetch that lands after its target was left", async () => {
    const { host, target, resolvers } = await switching([]);
    target.value = { container: "Sidebar", address: "sales", title: "Customize this sidebar" };
    await flush();
    target.value = { container: "Sidebar", address: "support", title: "Customize this sidebar" };
    await flush();

    resolvers[0]([item("stale")]);
    await flush();

    expect(rowKeys(host)).toEqual([]);
  });

  it("shows what a person hid, or a hide would be a one-way door", async () => {
    const { rowKeys } = await editor([item("a"), item("b", { hidden: 1 })]);

    expect(rowKeys()).toEqual(["a", "b"]);
  });

  it("saves the whole list it is showing, not the difference", async () => {
    // The reduction is the server's; the client sends the whole list.
    const editing = await editor([item("a"), item("b")]);
    runMethod.mockResolvedValue({ data: { rail: [], sidebars: {} } });

    await editing.click("Move a down");
    await editing.click("Save");

    expect(keys(editing.sent())).toEqual(["b", "a"]);
  });

  it("carries a rename as the row's label", async () => {
    const editing = await editor([item("a", { label: "Accounts" })]);
    runMethod.mockResolvedValue({ data: { rail: [], sidebars: {} } });

    await editing.type("Name of a", "Money");
    await editing.click("Save");

    expect(editing.sent()[0].label).toBe("Money");
  });

  it("toggles a hide both ways", async () => {
    const editing = await editor([item("a")]);
    runMethod.mockResolvedValue({ data: { rail: [], sidebars: {} } });

    await editing.click("Hide a");
    await editing.click("Save");
    expect(editing.sent()[0].hidden).toBe(1);

    await editing.click("Show a");
    await editing.click("Save");
    expect(editing.sent()[0].hidden).toBeUndefined();
  });

  it("hands the whole prefix's navigation back to the shell", async () => {
    const editing = await editor([item("a")]);
    const navigation = { rail: [item("a")], sidebars: {} };
    runMethod.mockResolvedValue({ data: navigation });

    await editing.click("Hide a");
    await editing.click("Save");

    expect(editing.saved).toEqual([navigation]);
  });

  it("says a load failed rather than showing an empty list", async () => {
    // An empty list is a real answer -- an app with nothing on its rail -- so a swallowed
    // failure would render a confident, false "nothing to arrange".
    runMethod.mockReset();
    runMethod.mockRejectedValue(new Error("nope"));

    const host = document.createElement("div");
    createApp({
      render: () =>
        h(CustomizeSidebarDialog, {
          target: { container: "Rail", address: "frappe", title: "Customize sidebar" },
        }),
    }).mount(host);
    await flush();

    expect(host.textContent).toContain("Could not load this list");
    expect(host.querySelector("[data-testid='customize']")).toBeNull();
  });
});
