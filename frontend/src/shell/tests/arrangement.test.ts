// The arrangement editor and the list operations under it (#42363).
//
// Mounted with Vue's own `createApp` into happy-dom rather than through `@vue/test-utils`,
// which this package does not have. The editor is small enough that the difference is a
// `nextTick` and a `querySelector`, and a new devDependency for one component is a cost the
// shell's singleton rules make everyone else pay too.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

// The real barrel drags the icon plugins in. `Button` is stubbed as the element it renders,
// keeping `aria-label` and `@click`, which is all these tests reach for.
vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  // A render function, not a `template`: vitest resolves `vue` to the runtime-only build,
  // which has no compiler, so a string template silently renders nothing at all.
  Button: {
    props: ["label", "icon", "variant", "loading"],
    emits: ["click"],
    setup: (props: { label?: string }, { emit }: { emit: (event: string) => void }) => () =>
      h("button", { onClick: () => emit("click") }, props.label ?? ""),
  },
}));

import { call as mockedCall } from "frappe-ui";
import AppRail from "../AppRail.vue";
import ArrangementEditor from "../ArrangementEditor.vue";
import { dropOn, move, saveArrangement, type ArrangedItem } from "@/arrangement";

const call = mockedCall as unknown as ReturnType<typeof vi.fn>;

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
  beforeEach(() => call.mockReset());

  it("sends the whole ordered list and the address it belongs to", async () => {
    call.mockResolvedValue({ rail: [], sidebars: {} });
    const items = [item("b"), item("a")];

    await saveArrangement({ container: "Sidebar", address: "module_def_core" }, items);

    expect(call).toHaveBeenCalledWith("frappe.shell.arrangement.save_arrangement", {
      container: "Sidebar",
      address: "module_def_core",
      scope: "user",
      items,
    });
  });

  it("defaults to a person's own layer, and never names a user", async () => {
    call.mockResolvedValue({ rail: [], sidebars: {} });

    await saveArrangement({ container: "Rail", address: "frappe" }, []);

    const [, args] = call.mock.calls[0];
    expect(args.scope).toBe("user");
    expect(args).not.toHaveProperty("user");
  });
});

async function editor(rows: ArrangedItem[]) {
  call.mockReset();
  call.mockResolvedValue(rows);

  const host = document.createElement("div");
  document.body.appendChild(host);
  const saved: unknown[] = [];
  const app = createApp({
    render: () =>
      h(ArrangementEditor, {
        container: "Rail",
        address: "frappe",
        title: "Arrange this rail",
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
    sent: () => call.mock.calls.at(-1)![1].items as ArrangedItem[],
  };
}

describe("the editor", () => {
  it("shows what a person hid, or a hide would be a one-way door", async () => {
    const { rowKeys } = await editor([item("a"), item("b", { hidden: 1 })]);

    expect(rowKeys()).toEqual(["a", "b"]);
  });

  it("saves the whole list it is showing, not the difference", async () => {
    // The reduction is the server's. A client that sent anchors would be computing identity
    // against a base it may be holding stale, which is desk v1's mistake in reverse.
    const editing = await editor([item("a"), item("b")]);
    call.mockResolvedValue({ rail: [], sidebars: {} });

    await editing.click("Move a down");
    await editing.click("Save");

    expect(keys(editing.sent())).toEqual(["b", "a"]);
  });

  it("carries a rename as the row's label", async () => {
    const editing = await editor([item("a", { label: "Accounts" })]);
    call.mockResolvedValue({ rail: [], sidebars: {} });

    await editing.type("Name of a", "Money");
    await editing.click("Save");

    expect(editing.sent()[0].label).toBe("Money");
  });

  it("toggles a hide both ways", async () => {
    const editing = await editor([item("a")]);
    call.mockResolvedValue({ rail: [], sidebars: {} });

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
    call.mockResolvedValue(navigation);

    await editing.click("Hide a");
    await editing.click("Save");

    expect(editing.saved).toEqual([navigation]);
  });

  it("says a load failed rather than showing an empty list", async () => {
    // An empty list is a real answer -- an app with nothing on its rail -- so a swallowed
    // failure would render a confident, false "nothing to arrange".
    call.mockReset();
    call.mockRejectedValue(new Error("nope"));

    const host = document.createElement("div");
    createApp({
      render: () =>
        h(ArrangementEditor, { container: "Rail", address: "frappe", title: "Arrange" }),
    }).mount(host);
    await flush();

    expect(host.textContent).toContain("Could not load this arrangement");
    expect(host.querySelector("[data-testid='arrangement']")).toBeNull();
  });
});

describe("the rail's way in", () => {
  function rail(arrangeable: boolean) {
    const host = document.createElement("div");
    const app = createApp({
      render: () => h(AppRail, { items: [], arrangeable }),
    });
    app.provide("boot", { app: arrangeable ? "frappe" : null });
    // A real router, because the rail's home link is a real `RouterLink` and resolves through
    // the injections a router provides. A memory history keeps it out of happy-dom's URL.
    app.use(
      createRouter({
        history: createMemoryHistory(),
        routes: [{ path: "/", name: "home", component: { render: () => null } }],
      })
    );
    app.mount(host);
    return host;
  }

  it("offers Arrange inside an app", () => {
    expect(rail(true).textContent).toContain("Arrange");
  });

  it("does not offer it on the index, which belongs to no app", () => {
    // `/apps` has no rail to arrange and no address to name one by: `boot.app` is null there
    // and `boot.navigation` is absent, so the button would open an editor addressed at nothing.
    expect(rail(false).textContent).not.toContain("Arrange");
  });
});
