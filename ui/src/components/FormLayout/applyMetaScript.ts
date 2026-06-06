import type { FieldMeta, FormLayoutSchema } from './types'

/**
 * Apply a list of declarative **meta operations** to a layout schema.
 *
 * This is the *meta/layout scripting* seam (distinct from field-change behaviour
 * scripting, which rides the `@change` commit funnel). The pipeline is:
 *
 *   buildLayoutFromMeta → [ applyMetaScript(schema, ops) ] → resolveLayout(doc) → FormLayout
 *
 * It runs **after** the structural build (the script sees the whole tree) and
 * **before** `resolveLayout` (so a script that flips `hidden`/`reqd`/`readOnly`
 * flows through the same `depends_on` baking and reactivity as everything else).
 *
 * Pure and total: walks the tree and returns a **fresh** schema; never mutates
 * its input (the schema from `useDoctypeLayout` is cached and shared). Ops that
 * match nothing are silently no-ops. This is the stable applier — declarative
 * patch ops only; an imperative `new Function` controller and server-side storage
 * are a later (syntax/evaluator) layer that produces these ops.
 */

export type MetaOp =
  /** Set any field-meta property by fieldname (`frm.set_df_property` analogue). */
  | { op: 'setFieldProperty'; fieldname: string; prop: keyof FieldMeta; value: unknown }
  /** Convenience: hide a field (shorthand for `setFieldProperty … 'hidden' true`). */
  | { op: 'hideField'; fieldname: string }
  /** Convenience: show a field. */
  | { op: 'showField'; fieldname: string }
  /** Insert a new field immediately after an existing one (same column). */
  | { op: 'addField'; field: FieldMeta; after: string }

/** Map every field through `fn`, rebuilding a fresh tree (input untouched). */
function mapFields(
  schema: FormLayoutSchema,
  fn: (field: FieldMeta) => FieldMeta,
): FormLayoutSchema {
  return schema.map((tab) => ({
    ...tab,
    sections: tab.sections.map((section) => ({
      ...section,
      columns: section.columns.map((column) => ({
        ...column,
        fields: column.fields.map(fn),
      })),
    })),
  }))
}

/** Insert `field` into whichever column holds `after`, right behind it. */
function insertFieldAfter(
  schema: FormLayoutSchema,
  field: FieldMeta,
  after: string,
): FormLayoutSchema {
  return schema.map((tab) => ({
    ...tab,
    sections: tab.sections.map((section) => ({
      ...section,
      columns: section.columns.map((column) => {
        const idx = column.fields.findIndex((f) => f.fieldname === after)
        if (idx === -1) return column
        const fields = [...column.fields]
        fields.splice(idx + 1, 0, { ...field })
        return { ...column, fields }
      }),
    })),
  }))
}

function applyOp(schema: FormLayoutSchema, op: MetaOp): FormLayoutSchema {
  switch (op.op) {
    case 'setFieldProperty':
      return mapFields(schema, (f) =>
        f.fieldname === op.fieldname ? { ...f, [op.prop]: op.value } : f,
      )
    case 'hideField':
      return mapFields(schema, (f) =>
        f.fieldname === op.fieldname ? { ...f, hidden: true } : f,
      )
    case 'showField':
      return mapFields(schema, (f) =>
        f.fieldname === op.fieldname ? { ...f, hidden: false } : f,
      )
    case 'addField':
      return insertFieldAfter(schema, op.field, op.after)
    default:
      return schema
  }
}

export function applyMetaScript(
  schema: FormLayoutSchema,
  ops: MetaOp[],
): FormLayoutSchema {
  return ops.reduce(applyOp, schema)
}
