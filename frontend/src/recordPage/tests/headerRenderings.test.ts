// The three header renderings and the fitting rule as executable claims.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HeaderActionsSurface,
  projectHeaderActions,
  renderingOf,
  resetHeaderWarnings,
  type HeaderNode,
} from "../headerRenderings";
import type { HeaderAction } from "../types";

const BUDGET = 2;

// A failing assertion never reaches its own `mockRestore`, and a console spy
// left installed collects the next test's warnings as if they were its own.
afterEach(() => {
  vi.restoreAllMocks();
});

// The warn-once memory is module state, so without this a case that reuses
// another's message reads an empty `mock.calls` and passes for the wrong reason.
beforeEach(() => {
  resetHeaderWarnings();
});

function action(name: string, extra: Partial<HeaderAction> = {}): HeaderAction {
  return { name, label: name, ...extra };
}

const button = (name: string, extra: Partial<HeaderAction> = {}) =>
  action(name, { display: "button", ...extra });

const dropdown = (name: string, extra: Partial<HeaderAction> = {}) =>
  action(name, { display: "dropdown", ...extra });

/** The surface's own shape: what `resolve()` hands the host. */
function resolved(items: HeaderAction[], ...hidden: string[]) {
  return items.map((item) => ({
    item,
    source: "test",
    hidden: hidden.includes(item.name),
  }));
}

function project(items: HeaderAction[], budget = BUDGET) {
  return projectHeaderActions(resolved(items), budget);
}

function controlNames(items: HeaderAction[], budget = BUDGET) {
  return project(items, budget).controls.map(
    (control) => `${control.kind}:${control.item.name}`
  );
}

function bandNames(items: HeaderAction[], budget = BUDGET) {
  return project(items, budget).bands.map(
    (band) => `${band.group}[${band.items.map(rendered).join(",")}]`
  );
}

/** A band's rows as one string, so nesting is visible in the expectation. */
function rendered(node: HeaderNode): string {
  if (!node.container) return node.item.name;
  return `${node.item.name}{${node.members.map(rendered).join(",")}}`;
}

describe("the three renderings", () => {
  it("gives a bare button, a dropdown of its own, and the shared menu", () => {
    const items = [
      button("refresh_quote"),
      dropdown("telephony"),
      action("call", { group: "telephony" }),
      action("sms", { group: "telephony" }),
      action("audit"),
    ];
    expect(controlNames(items)).toEqual([
      "button:refresh_quote",
      "dropdown:telephony",
    ]);
    expect(bandNames(items)).toEqual(["actions[audit]"]);
  });

  it("collects a dropdown's members wherever they sit in the flat list", () => {
    const items = [
      action("call", { group: "telephony" }),
      button("refresh_quote"),
      dropdown("telephony"),
      action("sms", { group: "telephony" }),
    ];
    const { controls } = project(items);
    const telephony = controls[1];
    expect(telephony.kind).toBe("dropdown");
    expect(
      telephony.kind === "dropdown" && telephony.members.map(rendered)
    ).toEqual(["call", "sms"]);
  });

  // A member never relocates the button it hangs off: the container's own position places it.
  it("places a dropdown by its own item, not by its first member", () => {
    const items = [
      action("sms", { group: "telephony" }),
      button("refresh_quote"),
      dropdown("telephony"),
    ];
    expect(controlNames(items)).toEqual([
      "button:refresh_quote",
      "dropdown:telephony",
    ]);
  });

  it("keeps the adjacency banding for everything that stays in the menu", () => {
    const items = [
      action("favourite", { group: "favourite" }),
      action("copy_url"),
      action("copy_id"),
      action("delete", { group: "delete" }),
    ];
    expect(bandNames(items)).toEqual([
      "favourite[favourite]",
      "actions[copy_url,copy_id]",
      "delete[delete]",
    ]);
  });

  it("keeps a dropdown's members out of the menu bands", () => {
    const items = [
      action("copy_url"),
      dropdown("telephony"),
      action("call", { group: "telephony" }),
      action("copy_id"),
    ];
    expect(bandNames(items)).toEqual(["actions[copy_url,copy_id]"]);
  });
});

describe("the fitting rule", () => {
  it("keeps the leading controls and demotes from the right", () => {
    const items = [button("one"), button("two"), button("three")];
    expect(controlNames(items)).toEqual(["button:one", "button:two"]);
    expect(bandNames(items)).toEqual(["three[three]"]);
  });

  it("demotes everything at budget 0, which is the mobile rule", () => {
    const items = [
      button("one"),
      dropdown("two"),
      action("call", { group: "two" }),
    ];
    expect(controlNames(items, 0)).toEqual([]);
    expect(bandNames(items, 0)).toEqual(["one[one]", "two[call]"]);
  });

  it("collapses a demoted dropdown whole, under its own label as a heading", () => {
    const items = [
      button("one"),
      button("two"),
      dropdown("telephony", { label: "Telephony" }),
      action("call", { group: "telephony" }),
      action("sms", { group: "telephony" }),
    ];
    const { bands } = project(items);
    expect(bands[0]).toMatchObject({ group: "telephony", label: "Telephony" });
    expect(bands[0].items.map(rendered)).toEqual(["call", "sms"]);
  });

  // The only band that carries a heading is a collapsed dropdown's.
  it("gives a demoted bare button a band with no heading", () => {
    const items = [
      button("one"),
      button("two"),
      button("three"),
      action("audit"),
    ];
    const { bands } = project(items);
    expect(bands[0]).toEqual({
      group: "three",
      items: [{ item: items[2], members: [] }],
    });
  });

  it("demotes several controls in their top-level order, ahead of the built-ins", () => {
    const items = [
      button("one"),
      button("two"),
      button("three"),
      button("four"),
      action("copy_url"),
    ];
    expect(bandNames(items)).toEqual([
      "three[three]",
      "four[four]",
      "actions[copy_url]",
    ]);
  });

  // A promoted built-in overflows on the same rule and does not return to its home band.
  it("demotes a promoted built-in to the front, not back to its own band", () => {
    const items = [
      button("one"),
      button("two"),
      action("copy_url"),
      button("delete", { group: "delete" }),
    ];
    expect(bandNames(items)).toEqual(["delete[delete]", "actions[copy_url]"]);
  });

  // An empty dropdown is a button that opens nothing.
  it("drops a dropdown with no visible members before the budget applies", () => {
    const items = [dropdown("telephony"), button("one"), button("two")];
    expect(controlNames(items)).toEqual(["button:one", "button:two"]);
    expect(bandNames(items)).toEqual([]);
  });

  // The container is above its members, as a hidden panelSection is above its
  // fields: hiding it removes the whole control, members and all.
  it("takes a hidden dropdown's members with it", () => {
    const items = [
      dropdown("telephony"),
      action("call", { group: "telephony" }),
      action("sms", { group: "telephony" }),
      action("copy_url"),
    ];
    const projection = projectHeaderActions(
      resolved(items, "telephony"),
      BUDGET
    );
    expect(projection.controls).toEqual([]);
    expect(projection.bands.map((band) => band.group)).toEqual(["actions"]);
  });

  // ...but a group naming no dropdown at all is still an invented menu band,
  // which is what a script writing `group: 'my_band'` has always got.
  it("leaves a group that names no dropdown as a band of its own", () => {
    const items = [
      action("audit", { group: "audit_band" }),
      action("copy_url"),
    ];
    expect(bandNames(items)).toEqual([
      "audit_band[audit]",
      "actions[copy_url]",
    ]);
  });
});

// A section is a container spelled the way a dropdown is, and a submenu is a
// container inside a container; both fall out of one rule.
describe("sections and submenus", () => {
  const section = (name: string, extra: Partial<HeaderAction> = {}) =>
    action(name, { display: "section", ...extra });

  it("titles a band with a top-level section, and charges it no budget", () => {
    const items = [
      button("one"),
      button("two"),
      section("danger", { label: "Danger" }),
      action("delete", { group: "danger" }),
      action("copy_url"),
    ];
    // Both buttons still fit: the section is not a control.
    expect(controlNames(items)).toEqual(["button:one", "button:two"]);
    const { bands } = project(items);
    expect(bands.map((band) => [band.group, band.label])).toEqual([
      ["danger", "Danger"],
      ["actions", undefined],
    ]);
    expect(bands[0].items.map(rendered)).toEqual(["delete"]);
  });

  it("gives a top-level dropdown a titled section among its members", () => {
    const items = [
      dropdown("tools", { label: "Deal Tools" }),
      action("snapshot", { group: "tools" }),
      section("danger", { label: "Danger", group: "tools" }),
      action("delete", { group: "danger" }),
    ];
    const { controls } = project(items);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
    ).toEqual(["snapshot", "danger{delete}"]);
  });

  it("renders a container inside a container as a submenu", () => {
    const items = [
      dropdown("tools", { label: "Deal Tools" }),
      dropdown("share", { label: "Share", group: "tools" }),
      action("share_email", { group: "share" }),
      action("share_link", { group: "share" }),
    ];
    const { controls } = project(items);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
    ).toEqual(["share{share_email,share_link}"]);
  });

  // `MenuOption` excludes `MenuGroupOption`, so a band cannot hold a titled
  // group; `MenuSubmenuOption` is a legal `MenuOption`.
  it("flattens a demoted dropdown's section and keeps its submenu", () => {
    const items = [
      button("one"),
      button("two"),
      dropdown("tools", { label: "Deal Tools" }),
      dropdown("share", { label: "Share", group: "tools" }),
      action("share_link", { group: "share" }),
      section("danger", { label: "Danger", group: "tools" }),
      action("delete", { group: "danger" }),
    ];
    const { bands } = project(items);
    expect(bands[0]).toMatchObject({ group: "tools", label: "Deal Tools" });
    expect(bands[0].items.map(rendered)).toEqual([
      "share{share_link}",
      "delete",
    ]);
  });

  // The same fact one level up: a band is a band wherever it came from.
  it("flattens a section inside a top-level section", () => {
    const items = [
      section("outer", { label: "Outer" }),
      section("inner", { label: "Inner", group: "outer" }),
      action("deep", { group: "inner" }),
    ];
    expect(bandNames(items)).toEqual(["outer[deep]"]);
  });

  it("takes a nested container and its members down with a hidden outer one", () => {
    const items = [
      dropdown("tools", { label: "Deal Tools" }),
      section("danger", { label: "Danger", group: "tools" }),
      action("delete", { group: "danger" }),
      action("copy_url"),
    ];
    const projection = projectHeaderActions(resolved(items, "tools"), BUDGET);
    expect(projection.controls).toEqual([]);
    expect(projection.bands.map((band) => band.group)).toEqual(["actions"]);
  });

  it("drops a section that has nothing in it", () => {
    const items = [section("danger", { label: "Danger" }), action("copy_url")];
    expect(bandNames(items)).toEqual(["actions[copy_url]"]);
  });

  it("warns about an unknown display and renders it in the menu", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items = [action("odd", { display: "flyout" as any })];
    expect(bandNames(items)).toEqual(["actions[odd]"]);
    expect(warn.mock.calls[0][0]).toContain("display: 'flyout'");
    warn.mockRestore();
  });

  // `MenuSubmenuOption` forbids `onClick` outright.
  it("warns that a container's run never fires", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items = [
      dropdown("noisy", { label: "Noisy", run: () => {} }),
      action("inside", { group: "noisy" }),
    ];
    project(items);
    expect(warn.mock.calls[0][0]).toContain("its `run` never fires");
    warn.mockRestore();
  });
});

// Clamped, never ignored: ignoring `group` would promote the container to a top-level control.
describe("the depth cap", () => {
  const section = (name: string, extra: Partial<HeaderAction> = {}) =>
    action(name, { display: "section", ...extra });

  it("moves a third-level container up to the deepest level it can reach", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items = [
      dropdown("d1", { label: "One" }),
      dropdown("d2", { label: "Two", group: "d1" }),
      dropdown("d3", { label: "Three", group: "d2" }),
      action("deep", { group: "d3" }),
    ];
    const { controls } = project(items);
    expect(controls.map((control) => control.item.name)).toEqual(["d1"]);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
      // `d2` is not here: clamping emptied it, and an empty dropdown is a
      // trigger that opens nothing.
    ).toEqual(["d3{deep}"]);
    expect(warn.mock.calls[0][0]).toContain("nests 3 containers deep");
    warn.mockRestore();
  });

  // Clamping is what produces an empty container, and an empty dropdown is a
  // trigger that opens nothing, at every level.
  it("drops the dropdown clamping emptied, at any depth", () => {
    const items = [
      dropdown("e1", { label: "One" }),
      dropdown("e2", { label: "Two", group: "e1" }),
      dropdown("e3", { label: "Three", group: "e2" }),
      action("leaf", { group: "e3" }),
    ];
    const { controls } = project(items);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
    ).toEqual(["e3{leaf}"]);
  });

  it("puts a `group` cycle in the menu rather than in the header row", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items = [
      dropdown("ping", { label: "Ping", group: "pong" }),
      dropdown("pong", { label: "Pong", group: "ping" }),
      action("inside", { group: "ping" }),
      action("other", { group: "pong" }),
      button("real"),
    ];
    // The cycle wins no slot: the one real control is the only control.
    expect(controlNames(items)).toEqual(["button:real"]);
    const { bands } = project(items);
    expect(bands.map((band) => [band.group, band.label])).toEqual([
      ["ping", "Ping"],
      ["pong", "Pong"],
    ]);
    expect(bands[0].items.map(rendered)).toEqual(["inside"]);
    expect(warn.mock.calls[0][0]).toContain("`group` cycle");
    warn.mockRestore();
  });

  // ...but an emptied *section* stays: frappe-ui drops a group with no options
  // of its own, and a section is the one container that can be empty harmlessly.
  it("clamps a section the same way, and leaves the emptied one standing", () => {
    const items = [
      dropdown("s1", { label: "One" }),
      section("s2", { label: "Two", group: "s1" }),
      section("s3", { label: "Three", group: "s2" }),
      action("deep", { group: "s3" }),
    ];
    const { controls } = project(items);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
    ).toEqual(["s2{}", "s3{deep}"]);
  });
});

// A block splices as a unit, the same shape `order(names[])` set.
describe("add takes a block", () => {
  it("splices the block as a unit at the anchor, in list order", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [action("copy_url"), action("delete")]);
    built.add(
      [
        dropdown("tools", { label: "Deal Tools" }),
        action("snapshot", { group: "tools" }),
        action("audit", { group: "tools" }),
      ],
      { before: "delete" }
    );
    expect(built.visible().map((item) => item.name)).toEqual([
      "copy_url",
      "tools",
      "snapshot",
      "audit",
      "delete",
    ]);
  });

  it("appends the block when the anchor names nothing", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [action("copy_url")]);
    built.add([action("a"), action("b")], { after: "nowhere" });
    expect(built.visible().map((item) => item.name)).toEqual([
      "copy_url",
      "a",
      "b",
    ]);
  });

  // The block is spliced one item at a time, so an anchor naming an item the
  // same block adds must still leave the block contiguous and in order.
  it("stays contiguous when the anchor is inside the block", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [action("copy_url"), action("delete")]);
    built.add([action("a"), action("b"), action("c")], { before: "b" });
    expect(built.visible().map((item) => item.name)).toEqual([
      "copy_url",
      "delete",
      "a",
      "b",
      "c",
    ]);
  });

  // The icon bridge and the raw-component guard run per item, or only the head of a block gets them.
  it("bridges every item's icon, not just the head's", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => []);
    built.add([
      action("a", { icon: "lucide-circle" }),
      action("b", { icon: "lucide-square" }),
    ]);
    expect(built.visible().map((item) => item.icon)).toEqual([
      "lucide-circle",
      "lucide-square",
    ]);
  });

  it("does nothing with an empty block", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [action("copy_url")]);
    built.add([]);
    expect(built.visible().map((item) => item.name)).toEqual(["copy_url"]);
  });

  // The anchor belongs to the block, not to each item in it: claiming it for
  // every item would report an anchor the tail was never given.
  it("warns about the block's anchor once, for its head", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [button("refresh_quote"), action("delete")]);
    built.add(
      [
        dropdown("tools", { label: "Deal Tools" }),
        action("snapshot", { group: "tools" }),
        action("audit", { group: "tools" }),
      ],
      { after: "delete" }
    );
    built.visible();
    expect(warn.mock.calls.map((call) => call[0])).toEqual([
      expect.stringContaining("headerActions.add('tools')"),
    ]);
    warn.mockRestore();
  });

  it("stages a block in a replay and swaps it in whole", () => {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => [action("copy_url")]);
    built.beginReplay();
    built.add([action("a"), action("b")]);
    // The self-read resolves over the replay in flight.
    expect(built.has("b")).toBe(true);
    built.commitReplay();
    expect(built.visible().map((item) => item.name)).toEqual([
      "copy_url",
      "a",
      "b",
    ]);
  });
});

// The one rule again, from the other end: `group` decides where an item goes,
// and `display` only decides what it looks like once it is there.
describe("group beats display", () => {
  it("makes a button inside a dropdown an ordinary row, and says so", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    project([
      dropdown("holder", { label: "Holder" }),
      button("stray", { group: "holder" }),
    ]);
    expect(warn.mock.calls[0][0]).toContain("is a button inside 'holder'");
    warn.mockRestore();
  });

  it("makes a button inside a dropdown an ordinary row", () => {
    const items = [
      dropdown("tools", { label: "Tools" }),
      button("inside", { group: "tools" }),
      button("outside"),
    ];
    expect(controlNames(items)).toEqual(["dropdown:tools", "button:outside"]);
    const { controls } = project(items);
    expect(
      controls[0].kind === "dropdown" && controls[0].members.map(rendered)
    ).toEqual(["inside"]);
  });

  it("buries a member two containers down with the outermost one", () => {
    const items = [
      dropdown("outer", { label: "Outer" }),
      dropdown("middle", { label: "Middle", group: "outer" }),
      action("leaf", { group: "middle" }),
      action("copy_url"),
    ];
    const projection = projectHeaderActions(resolved(items, "outer"), BUDGET);
    expect(projection.controls).toEqual([]);
    expect(projection.bands.map((band) => band.group)).toEqual(["actions"]);
  });
});

describe("the cross-rendering anchor warning", () => {
  function surface(items: HeaderAction[]) {
    const built = new HeaderActionsSurface();
    built.provideBuiltins(() => items);
    return built;
  }

  it("warns when an anchor renders somewhere else, and still splices", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([button("refresh_quote"), action("delete")]);
    built.add(action("escalate"), { after: "refresh_quote" });
    expect(built.visible().map((item) => item.name)).toEqual([
      "refresh_quote",
      "escalate",
      "delete",
    ]);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("a top-level button");
    expect(warn.mock.calls[0][0]).toContain("an entry in the ⋯ menu");
    warn.mockRestore();
  });

  it("says nothing when both items render the same way", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([action("copy_url"), action("delete")]);
    built.add(action("escalate"), { after: "copy_url" });
    built.visible();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  // Checked against the final list, not at call time: a member can be added
  // before the container that decides its rendering.
  it("resolves the rendering over the final list", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([button("refresh_quote")]);
    built.add(action("call", { group: "telephony" }), {
      after: "refresh_quote",
    });
    built.add(dropdown("telephony", { label: "Telephony" }));
    built.visible();
    expect(warn.mock.calls[0][0]).toContain("“Telephony” dropdown");
    warn.mockRestore();
  });

  // Anchoring a member at its own container is how an author says "first in
  // this dropdown", and it does exactly that.
  it("says nothing when a member is anchored at its own container", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([dropdown("telephony", { label: "Telephony" })]);
    built.add(action("sms", { group: "telephony" }), { after: "telephony" });
    built.visible();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  // ...and the converse: a dropdown button and a bare button are ordered
  // together by the fitting rule, so they are one rendering.
  it("says nothing between a bare button and a dropdown button", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([dropdown("telephony", { label: "Telephony" })]);
    built.add(button("escalate"), { after: "telephony" });
    built.visible();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("warns once however often the list is resolved", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const built = surface([button("refresh_quote")]);
    built.add(action("escalate"), { after: "refresh_quote" });
    built.visible();
    built.visible();
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it("drops the claims a replay rebuilt the list without", () => {
    const built = surface([button("refresh_quote")]);
    built.add(action("escalate"), { after: "refresh_quote" });
    built.beginReplay();
    built.commitReplay();
    expect(built.visible().map((item) => item.name)).toEqual(["refresh_quote"]);
  });
});

// An undeclared `group` synthesises an anonymous container, so every shipped
// script renders exactly as it did before sections existed.
describe("the undeclared branch renders as it always did", () => {
  const shipped = [
    button("refresh_quote"),
    dropdown("telephony", { label: "Telephony" }),
    action("call", { group: "telephony" }),
    action("sms", { group: "telephony" }),
    action("favourite", { group: "favourite" }),
    action("copy_url"),
    action("copy_id"),
    action("audit", { group: "audit_band" }),
    action("delete", { group: "delete" }),
  ];

  it("bands by adjacency and titles nothing", () => {
    const { controls, bands } = project(shipped);
    expect(
      controls.map((control) => `${control.kind}:${control.item.name}`)
    ).toEqual(["button:refresh_quote", "dropdown:telephony"]);
    expect(bandNames(shipped)).toEqual([
      "favourite[favourite]",
      "actions[copy_url,copy_id]",
      "audit_band[audit]",
      "delete[delete]",
    ]);
    expect(bands.every((band) => band.label === undefined)).toBe(true);
  });

  it("leaves every band flat, with no container among its rows", () => {
    const { bands } = project(shipped);
    const rows = bands.flatMap((band) => band.items);
    expect(rows.every((node) => node.container === undefined)).toBe(true);
    expect(rows.every((node) => node.members.length === 0)).toBe(true);
  });

  it("says nothing while doing it", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    project(shipped);
    project(shipped, 0);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("renderingOf", () => {
  // Read off the declared display, never the effective one, so nothing
  // computed from it can become width-dependent.
  it("answers from the declared display alone", () => {
    const items = [button("one"), button("two"), button("three")];
    expect(renderingOf(items[2], items)).toBe("row");
  });

  it("puts a member in its container's rendering", () => {
    const items = [
      dropdown("telephony"),
      action("call", { group: "telephony" }),
    ];
    expect(renderingOf(items[1], items)).toBe("container:telephony");
  });

  it("leaves a group that names no dropdown in the menu", () => {
    const items = [action("call", { group: "elsewhere" })];
    expect(renderingOf(items[0], items)).toBe("menu");
  });
});
