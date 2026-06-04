import { evaluateDependsOn } from './dependsOn'
import type { Column, FieldMeta, FormLayoutSchema, Section, Tab } from './types'

/**
 * Bake conditional visibility into a layout schema against the live `doc`.
 *
 * Pure and total: walks tabs → sections → columns → fields and returns a
 * **fresh** tree with `hidden` / `reqd` / `readOnly` resolved on each node. It
 * never mutates its input — the schema from `useDoctypeLayout` is cached and
 * shared, and returning new object identities lets Vue see the change.
 *
 * Resolution rules (a node with no expressions passes through unchanged):
 * - field `hidden` = `depends_on` false (else its static `hidden`);
 * - field `reqd` = static `reqd` OR `mandatory_depends_on` true;
 * - field `readOnly` = static `readOnly` OR `read_only_depends_on` true;
 * - section / tab `hidden` = its static `hidden` OR `depends_on` false.
 */
export function resolveLayout(
  schema: FormLayoutSchema,
  doc: Record<string, any>,
): FormLayoutSchema {
  const resolveField = (f: FieldMeta): FieldMeta => ({
    ...f,
    hidden: f.dependsOn ? !evaluateDependsOn(f.dependsOn, doc) : f.hidden,
    reqd: f.reqd || (!!f.mandatoryDependsOn && evaluateDependsOn(f.mandatoryDependsOn, doc)),
    readOnly:
      f.readOnly || (!!f.readOnlyDependsOn && evaluateDependsOn(f.readOnlyDependsOn, doc)),
  })

  const resolveColumn = (c: Column): Column => ({
    ...c,
    fields: c.fields.map(resolveField),
  })

  const resolveSection = (s: Section): Section => ({
    ...s,
    hidden: s.hidden || (!!s.dependsOn && !evaluateDependsOn(s.dependsOn, doc)),
    columns: s.columns.map(resolveColumn),
  })

  const resolveTab = (t: Tab): Tab => ({
    ...t,
    hidden: t.hidden || (!!t.dependsOn && !evaluateDependsOn(t.dependsOn, doc)),
    sections: t.sections.map(resolveSection),
  })

  return schema.map(resolveTab)
}
