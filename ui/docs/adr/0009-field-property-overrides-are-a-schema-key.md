# Field property overrides are a schema key, not a meta script

An app that wants to hide, lock or require a field **at runtime** now writes a
`FieldOverride` onto the layout node, and `resolveFieldConditionals` applies it
last. The meta-script route that tried to do this before — `applyMetaScript`,
`useScriptedLayout` and `useDoctypeLayout` — is **removed**, not deprecated.

## Why the meta-script route could not work

`applyMetaScript` mutated the built schema **before** `resolveLayout`. Since
`FormLayout` re-runs `resolveLayout` on every `doc` change, `depends_on` /
`mandatory_depends_on` / `read_only_depends_on` simply recomputed over whatever
the script had written, on the next keystroke. A `setFieldProperty("qty",
"hidden", 0)` on a field with a `depends_on` was silently undone.

Its patch vocabulary was also **open** (`[key: string]: any`, camelCase), so a
typo was indistinguishable from a property, and it could write keys the
renderers do not read.

Nothing in `frappe`, `crm`, `gameplan` or `audit` called it.

## What replaces it

```ts
import type { FieldOverride } from "@framework/ui/FormLayout";

// Plain data on the node. FormLayout reads it off the schema and knows
// nothing about who wrote it.
const node: FieldNode = {
  fieldname: "discount",
  fieldtype: "Currency",
  dependsOn: "eval:doc.has_discount",
  override: { hidden: false },   // wins over depends_on
};
```

**Enumerated, three keys:** `hidden`, `readOnly`, `reqd`. Those are the only
properties `resolveLayout` recomputes per render. `label`, `options`,
`precision`, `placeholder`, `description` and `filters` are set once when the
node is built and never recomputed, so an app sets them at build time (a
`Decorator`, or its own schema) rather than through an override.

**Applied last, on purpose.** It is the only override in this pipeline that is
not monotonic-restrictive — the one thing that can turn a conditional result
*off*.

**It cannot lift a permission floor.** A permlevel denial arrives as a static
`hidden` / `readOnly` flag plus `permDenied` on the field; an override that
would lift that flag is refused outright and warned about in DEV. Note the test
is `permDenied` and not `permlevel`: a reader who *has* the level is left
untouched by the gate, and a layout built straight from meta was never gated at
all, so a level-based test would refuse legitimate overrides on both.

## Migration

| removed | replacement |
|---|---|
| `applyMetaScript(schema, ops)` | `FieldNode.override` on the node, applied by `resolveFieldConditionals` |
| `MetaOp` (`setFieldProperty`, `showField`, `hideField`) | `override: { hidden, readOnly, reqd }` |
| `MetaOp` (`addField`, `moveField`) | no replacement — a layout that adds a field is inventing a docfield. Change the Form Layout, or the doctype |
| `useScriptedLayout(doctype, ops)` | build the layout (`buildLayoutFromMeta`, or the stored-layout source) and attach `override` to the nodes you want to change |
| `useDoctypeLayout(doctype)` | `useDoctypeMeta(doctype)` + `buildLayoutFromMeta(meta.fields, { childMetas })` — which is all it did, plus a memo |
| `UseDoctypeLayout` | — |

## Not shipped as a deprecation shim

Deliberate. `@framework/ui` is **not a published package** — consumers link it
off the filesystem (`"@framework/ui": "link:../../frappe/ui"`), so it moves in
lockstep with the frappe checkout. There is no version a consumer can pin, and
therefore no release in which a deprecated export could ever be removed: a shim
would be permanent.

More to the point, a shim for `applyMetaScript` means keeping `setFieldProperty`
alive, and shipping two competing field-override designs side by side is exactly
what this change exists to prevent. A removed import fails loudly at build time,
at the import, with the name in the message — and this table says what to do
next.
