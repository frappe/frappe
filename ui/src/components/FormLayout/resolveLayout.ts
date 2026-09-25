import { evaluateDependsOn } from "./dependsOn";
import type {
  Column,
  FieldMeta,
  FieldNode,
  FieldOverride,
  FormLayoutSchema,
  Section,
  Tab,
} from "./types";

/**
 * The permission floor an override may not cross.
 *
 * A denial reaches the layout as a static `hidden` / `readOnly`, which is
 * indistinguishable from a meta-hidden or meta-read-only field — so the test is
 * `permDenied`, the flag whoever applied the gate set on the fields it actually
 * denied. Not `permlevel`: a reader who *has* the level is left untouched, and
 * a layout built straight from meta was never gated at all, so testing the
 * level would refuse legitimate overrides on both.
 *
 * `key` is what the override is trying to turn off; the floor only applies when
 * that same flag is the one carrying the denial (a `read` denial sets
 * `readOnly` and says nothing about `hidden`).
 */
function isFloor(f: FieldMeta, key: "hidden" | "readOnly" | "reqd"): boolean {
  return !!f.permDenied && (key === "reqd" ? !!f.readOnly : !!f[key]);
}

/** One warning per field per key — `resolveLayout` re-runs on every keystroke. */
const warned = new Set<string>();

function warnRefused(f: FieldMeta, key: string, wanted: boolean): void {
  if (!import.meta.env.DEV) return;
  const once = `${f.fieldname}:${key}`;
  if (warned.has(once)) return;
  warned.add(once);
  console.warn(
    `[FormLayout] ignored override.${key} = ${wanted} on "${f.fieldname}": ` +
      `permlevel ${f.permlevel ?? "?"} denies access, which an override cannot lift.`
  );
}

/** Apply one override key over the resolved value, honouring the floor. */
function applyOverride(
  f: FieldMeta,
  key: "hidden" | "readOnly",
  resolved: boolean | undefined,
  wanted: boolean | undefined
): boolean | undefined {
  if (wanted === undefined) return resolved;
  if (wanted === false && isFloor(f, key)) {
    warnRefused(f, key, wanted);
    return resolved;
  }
  return wanted;
}

/**
 * `reqd` has a floor too, from the other direction: demanding a field the
 * reader was denied write access to is a form that can never be submitted.
 */
function applyReqd(
  f: FieldMeta,
  resolved: boolean | undefined,
  wanted: boolean | undefined
): boolean | undefined {
  if (wanted === undefined) return resolved;
  if (wanted === true && isFloor(f, "reqd")) {
    warnRefused(f, "reqd", wanted);
    return resolved;
  }
  return wanted;
}

/** Test seam: the warn-once memory is module state. */
export function resetOverrideWarnings(): void {
  warned.clear();
}

/**
 * Bake a single field's conditional expressions (`depends_on` /
 * `mandatory_depends_on` / `read_only_depends_on`) against `doc`, returning a
 * **fresh** `FieldMeta` with `hidden` / `reqd` / `readOnly` resolved. Pure; a
 * field with no expressions passes through unchanged.
 *
 * Resolution rules:
 * - `hidden` = static `hidden` OR `depends_on` false;
 * - `reqd` = static `reqd` OR `mandatory_depends_on` true;
 * - `readOnly` = static `readOnly` OR `read_only_depends_on` true.
 *
 * Shared by `resolveLayout` (whole form, against the doc) and `TableField`'s
 * grid cells (per row, against each child row) so a conditionally
 * read-only/hidden/mandatory field resolves identically in the grid cell and
 * the row-edit dialog — the dialog evaluates the same expressions against the
 * same row clone, so both paths must agree (cf. `pickSiblingValue`).
 *
 * `doc` is the local record; `parent` is the enclosing doc — for a grid cell
 * the parent doc, for a top-level field its own doc — so a child-row expression
 * can reach a parent field via `parent.x` (see `evaluateDependsOn`). Defaults to
 * `doc` to mirror desk's top-level `parent === doc`.
 */
export function resolveFieldConditionals<
  T extends FieldMeta & { override?: FieldOverride },
>(f: T, doc: Record<string, any>, parent: Record<string, any> = doc): T {
  // Generic in the node type so a `FieldNode`'s `ui` overlay rides through the
  // spread (it does at runtime — `ui` is just another own-key) and stays typed.

  // Static `hidden` is a hard floor: a meta-hidden field stays hidden even
  // when its `depends_on` evaluates true (matches desk; these fields are now
  // kept in the schema, so `depends_on` must not silently un-hide them).
  const hidden = f.dependsOn
    ? f.hidden || !evaluateDependsOn(f.dependsOn, doc, parent)
    : f.hidden;
  const reqd =
    f.reqd ||
    (!!f.mandatoryDependsOn &&
      evaluateDependsOn(f.mandatoryDependsOn, doc, parent));
  const readOnly =
    f.readOnly ||
    (!!f.readOnlyDependsOn &&
      evaluateDependsOn(f.readOnlyDependsOn, doc, parent));

  const override = f.override;
  if (!override) return { ...f, hidden, reqd, readOnly };

  // Last word, on purpose: the override is the only thing here that can turn a
  // conditional result off, which is what lets an app beat `depends_on`.
  return {
    ...f,
    hidden: applyOverride(f, "hidden", hidden, override.hidden),
    reqd: applyReqd(f, reqd, override.reqd),
    readOnly: applyOverride(f, "readOnly", readOnly, override.readOnly),
  };
}

/**
 * Bake conditional visibility into a layout schema against the live `doc`.
 *
 * Pure and total: walks tabs → sections → columns → fields and returns a
 * **fresh** tree with `hidden` / `reqd` / `readOnly` resolved on each node. It
 * never mutates its input — a built schema is cached and shared by its source,
 * and returning new object identities lets Vue see the change.
 *
 * Resolution rules (a node with no expressions passes through unchanged):
 * - field-level rules: see `resolveFieldConditionals`;
 * - section / tab `hidden` = its static `hidden` OR `depends_on` false.
 *
 * `parent` is the enclosing doc (the row dialog passes the parent doc so a
 * child's `parent.x` resolves); it defaults to `doc` for a top-level form,
 * matching desk's `parent === doc`.
 */
export function resolveLayout(
  schema: FormLayoutSchema,
  doc: Record<string, any>,
  parent: Record<string, any> = doc
): FormLayoutSchema {
  const resolveField = (f: FieldNode): FieldNode =>
    resolveFieldConditionals(f, doc, parent);

  const resolveColumn = (c: Column): Column => ({
    ...c,
    fields: c.fields.map(resolveField),
  });

  const resolveSection = (s: Section): Section => ({
    ...s,
    hidden:
      s.hidden ||
      (!!s.dependsOn && !evaluateDependsOn(s.dependsOn, doc, parent)),
    columns: s.columns.map(resolveColumn),
  });

  const resolveTab = (t: Tab): Tab => ({
    ...resolveTabConditionals(t, doc, parent),
    sections: t.sections.map(resolveSection),
  });

  return schema.map(resolveTab);
}

/**
 * Bake one tab's conditional visibility against `doc`, returning a **fresh**
 * `Tab` with `hidden` resolved: static `hidden` OR `depends_on` false. Pure.
 *
 * Exported because the Record page's `page.formTabs` answers "is this one tab on
 * screen" without resolving the whole form, and the two must not drift.
 */
export function resolveTabConditionals(
  t: Tab,
  doc: Record<string, any>,
  parent: Record<string, any> = doc
): Tab {
  return {
    ...t,
    hidden:
      t.hidden ||
      (!!t.dependsOn && !evaluateDependsOn(t.dependsOn, doc, parent)),
  };
}

/**
 * A tab's visibility and label as the strip shows them: the values resolved
 * above, with a per-render `override` as the last word — the only thing here
 * that can lift a `depends_on`, mirroring `FieldOverride`.
 *
 * Applied by `FormLayout` rather than by `resolveLayout`: see `TabOverride`.
 */
export function applyTabOverride(t: Tab): { hidden: boolean; label: string } {
  return {
    hidden: t.override?.hidden ?? !!t.hidden,
    label: t.override?.label ?? t.label ?? "",
  };
}
