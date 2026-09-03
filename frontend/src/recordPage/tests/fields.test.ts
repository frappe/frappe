// The fields surface as executable claims: an enumerated snake_case patch, a
// render-time overlay cleared by the replay, and a permlevel floor.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
}));

import { markRaw } from "vue";
import { FieldsSurface, resetFieldWarnings } from "../fields";
import type { FieldsSurfaceHost } from "../fields";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";

const FIELDS: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", options: "Open\nWon" },
  { fieldname: "qty", fieldtype: "Int" },
  { fieldname: "rate", fieldtype: "Currency", depends_on: "eval:doc.qty > 0" },
  { fieldname: "secret", fieldtype: "Data", permlevel: 1 },
];

function makeSurface(
  host: Partial<FieldsSurfaceHost> = {},
): FieldsSurface {
  return new FieldsSurface({
    fields: () => FIELDS,
    doc: () => ({ qty: 0 }),
    fieldAccess: (): FieldAccess => "write",
    ...host,
  });
}

beforeEach(() => {
  resetFieldWarnings();
  vi.restoreAllMocks();
});

describe("the patch vocabulary", () => {
  it("splits a patch across the three points it is applied at", () => {
    const fields = makeSurface();
    fields.update("status", {
      read_only: true,
      label: "Stage",
      link_filters: { company: "Frappe" },
      props: { variant: "subtle" },
    });
    expect(fields.resolve().status).toEqual({
      override: { readOnly: true },
      meta: { label: "Stage", filters: { company: "Frappe" } },
      ui: { props: { variant: "subtle" } },
    });
  });

  it("takes `precision` as a number or the string a script may reach for", () => {
    const fields = makeSurface();
    fields.update("qty", { precision: "2" });
    expect(fields.resolve().qty.meta).toEqual({ precision: 2 });
  });

  it("carries a patch's payload through by identity, not deep-proxied", () => {
    // Anything a script puts in `props` reaches `v-bind`; a deep reactive
    // wrapper there breaks a nested component's internal slots.
    const props = { icon: markRaw({ name: "Icon" }) };
    const fields = makeSurface();
    fields.update("qty", { props });
    expect(fields.resolve().qty.ui?.props).toBe(props);
  });

  it("drops a key that is not a field property a script may set", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface();
    fields.update("status", { hidden: true, fieldtype: "Data" } as any);
    expect(fields.resolve().status).toEqual({ override: { hidden: true } });
    expect(warn.mock.calls[0][0]).toContain("fieldtype");
  });

  it("names a field the doctype does not have, and still records nothing that renders", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    makeSurface().hide("nope");
    expect(warn.mock.calls[0][0]).toContain('page.fields.hide("nope")');
  });

  it("stays quiet while the meta is still loading", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface({ fields: () => undefined });
    fields.hide("status");
    expect(warn).not.toHaveBeenCalled();
    // Recorded anyway: the meta lands later and the join applies it then.
    expect(fields.resolve().status).toEqual({ override: { hidden: true } });
  });
});

// A fieldname and a patch key are both strings a script chooses, and both were
// indexed into object literals — where four of them are inherited members.
describe("names that are not names", () => {
  it("keeps a `__proto__` fieldname out of Object.prototype", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface();
    fields.hide("__proto__");
    const patches = fields.resolve();

    // `resolveFieldConditionals` reads `override` off the prototype chain, so one
    // such write would hide a field in every form for the rest of the session.
    expect(({} as any).override).toBeUndefined();
    // Recorded as an ordinary own key instead — inert, since no field can be
    // named this, and attributable rather than invisible.
    expect(Object.hasOwn(patches, "__proto__")).toBe(true);
    expect(Object.getPrototypeOf(patches)).toBe(Object.prototype);
  });

  it("drops an inherited patch key instead of letting it through unwarned", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface();
    fields.update("qty", { toString: "hi", constructor: 1 } as any);

    expect(fields.resolve().qty).toEqual({});
    expect(warn.mock.calls.map((call) => call[0]).join()).toContain("toString");
  });

  it("does not address a layout break, which never reaches the renderer", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface({
      fields: () => [
        ...FIELDS,
        { fieldname: "sb_1", fieldtype: "Section Break" },
      ],
    });
    expect(fields.has("sb_1")).toBe(false);
    expect(fields.get("sb_1")).toBeNull();
  });
});

describe("the verbs", () => {
  it("reads `hide` and `show` as the same override, last one winning", () => {
    const fields = makeSurface();
    fields.hide("status");
    fields.show("status");
    expect(fields.resolve().status).toEqual({ override: { hidden: false } });
  });

  it("merges two patches for one field key by key", () => {
    const fields = makeSurface();
    fields.update("status", { label: "Stage", read_only: true });
    fields.update("status", { label: "Phase" });
    expect(fields.resolve().status).toEqual({
      meta: { label: "Phase" },
      override: { readOnly: true },
    });
  });

  it("answers `has` from the doctype's fields", () => {
    const fields = makeSurface();
    expect(fields.has("qty")).toBe(true);
    expect(fields.has("nope")).toBe(false);
  });

  it("clears every override on replay — and why a script needs no else", () => {
    const fields = makeSurface();
    fields.hide("status");
    fields.update("qty", { label: "Quantity" });
    fields.beginReplay();
    fields.commitReplay();
    expect(fields.resolve()).toEqual({});
  });

  // The overlay used to empty on `reset()` and refill a microtask later: a
  // script-hidden field visible for a tick on every save.
  it("keeps the applied overlay whole while a replay is in flight", () => {
    const fields = makeSurface();
    fields.hide("status");
    fields.beginReplay();
    expect(fields.resolve().status).toEqual({ override: { hidden: true } });
    fields.hide("status");
    expect(fields.resolve().status).toEqual({ override: { hidden: true } });
    fields.commitReplay();
    expect(fields.resolve().status).toEqual({ override: { hidden: true } });
  });

  it("publishes only on the outermost commit of a nested replay", () => {
    const fields = makeSurface();
    fields.beginReplay();
    fields.update("qty", { label: "Quantity" });
    fields.beginReplay();
    fields.update("qty", { label: "Nested" });
    fields.commitReplay();
    expect(fields.resolve()).toEqual({});
    fields.commitReplay();
    expect(fields.resolve().qty).toEqual({ meta: { label: "Nested" } });
  });
});

describe("get — the reader", () => {
  it("speaks the vocabulary the writer speaks, not the pipeline's", () => {
    const fields = makeSurface();
    fields.update("status", { read_only: true, label: "Stage" });
    expect(fields.get("status")).toMatchObject({
      fieldname: "status",
      fieldtype: "Select",
      label: "Stage",
      read_only: true,
      options: "Open\nWon",
    });
  });

  // The host renders the committed overlay, but a source reading its own work
  // back mid-replay must see it.
  it("reads the replay in flight, not the overlay the host is still rendering", () => {
    const fields = makeSurface();
    fields.update("status", { label: "Stage" });
    fields.beginReplay();
    fields.update("status", { label: "Rebuilt" });
    expect(fields.get("status")).toMatchObject({ label: "Rebuilt" });
    expect(fields.resolve().status).toEqual({ meta: { label: "Stage" } });
  });

  it("reads back what the setter wrote — the v1 asymmetry this exists to avoid", () => {
    const fields = makeSurface();
    expect(fields.get("qty")?.hidden).toBe(false);
    fields.hide("qty");
    expect(fields.get("qty")?.hidden).toBe(true);
  });

  it("resolves `depends_on`, and lets the override beat it", () => {
    const fields = makeSurface();
    // `qty` is 0, so `rate`'s condition is false and the field is hidden.
    expect(fields.get("rate")?.hidden).toBe(true);
    fields.show("rate");
    expect(fields.get("rate")?.hidden).toBe(false);
  });

  it("refuses to lift a permlevel denial", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface({
      fieldAccess: (fieldname) => (fieldname === "secret" ? "none" : "write"),
    });
    fields.show("secret");
    expect(fields.get("secret")?.hidden).toBe(true);
  });

  it("hands back a read-only snapshot", () => {
    const snapshot = makeSurface().get("status")!;
    expect(() => {
      (snapshot as any).label = "Stage";
    }).toThrow("is read-only");
  });

  it("reports the component the host's decorator mounts, not a plain node", () => {
    const Button = { name: "Button" };
    const fields = makeSurface({
      decorate: (field) =>
        field.fieldname === "qty" ? { component: Button } : undefined,
    });
    // Without the decorator the reader would answer `undefined` while the
    // renderer mounts a component — the asymmetry `get` exists to abolish.
    expect(fields.get("qty")?.component).toBe(Button);
  });

  it("hands a component back by identity, not wrapped in the read-only proxy", () => {
    const Button = markRaw({ name: "Button" });
    const fields = makeSurface();
    fields.update("qty", { component: Button });
    expect(fields.get("qty")?.component).toBe(Button);
  });

  it("is null for a field the doctype does not have", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(makeSurface().get("nope")).toBeNull();
  });

  it("carries none of the pipeline's internals", () => {
    const snapshot = makeSurface().get("rate")! as Record<string, unknown>;
    for (const internal of ["dependsOn", "permDenied", "override", "readOnly"])
      expect(snapshot[internal]).toBeUndefined();
  });
});
