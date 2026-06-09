import { evaluateDependsOn } from "./dependsOn";
import type {
  Column,
  FieldMeta,
  FormLayoutSchema,
  Section,
  Tab,
} from "./types";

/**
 * Bake a single field's conditional expressions (`depends_on` /
 * `mandatory_depends_on` / `read_only_depends_on`) against `doc`, returning a
 * **fresh** `FieldMeta` with `hidden` / `reqd` / `readOnly` resolved. Pure; a
 * field with no expressions passes through unchanged.
 *
 * Resolution rules:
 * - `hidden` = `depends_on` false (else its static `hidden`);
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
export function resolveFieldConditionals(
  f: FieldMeta,
  doc: Record<string, any>,
  parent: Record<string, any> = doc
): FieldMeta {
  return {
    ...f,
    hidden: f.dependsOn
      ? !evaluateDependsOn(f.dependsOn, doc, parent)
      : f.hidden,
    reqd:
      f.reqd ||
      (!!f.mandatoryDependsOn &&
        evaluateDependsOn(f.mandatoryDependsOn, doc, parent)),
    readOnly:
      f.readOnly ||
      (!!f.readOnlyDependsOn &&
        evaluateDependsOn(f.readOnlyDependsOn, doc, parent)),
  };
}

/**
 * Bake conditional visibility into a layout schema against the live `doc`.
 *
 * Pure and total: walks tabs → sections → columns → fields and returns a
 * **fresh** tree with `hidden` / `reqd` / `readOnly` resolved on each node. It
 * never mutates its input — the schema from `useDoctypeLayout` is cached and
 * shared, and returning new object identities lets Vue see the change.
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
  const resolveField = (f: FieldMeta): FieldMeta =>
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
    ...t,
    hidden:
      t.hidden ||
      (!!t.dependsOn && !evaluateDependsOn(t.dependsOn, doc, parent)),
    sections: t.sections.map(resolveSection),
  });

  return schema.map(resolveTab);
}
