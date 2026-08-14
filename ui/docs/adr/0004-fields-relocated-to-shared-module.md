# Fieldtype value-inputs are promoted to a shared `Fields` module

The fieldtype-aware value-input components currently in
`src/components/FormLayout/fields/` are lifted into their own
`@framework/ui` module so both **FormLayout** and the ListView **Filter** /
**Quick Filter** controls consume them, instead of Filter reaching across the
module boundary into FormLayout's internals. This mirrors the one-module-per-
concern layout of [ADR-0002](0002-listview-module-layout.md) (`SortBy/`,
`FileUpload/`, etc.) and makes the value inputs a first-class shared surface.

**Target location:** `src/components/Fields/` (sibling of `FormLayout/`, `Link/`,
`SortBy/`). It receives:

- the 23 value-input `*.vue` components (CheckField, SelectField, LinkField,
  DateField, DatetimeField, NumberField, DurationField, RatingField, TextField,
  … through the deep-injection TableField/GeolocationField/TableMultiSelectField);
- `fieldTypes.ts` — the fieldtype → component dispatch registry;
- `fieldtypeToLanguage.ts` and its test;
- a `Fields/types.ts` holding the field contract (`FieldMeta`,
  `FieldComponentProps`, `FieldComponentEmits`) **and** the form-context injection
  keys (`DocKey`, `ParentDocKey`, `UpdateKey`) — these are consumed by the field
  components, so they live with them; FormLayout imports them from here.

**Export surface:** add `"./fields"` to `package.json` `exports`, pointing at
`./src/components/Fields/index.ts` (mirroring the `./SortBy` entry). `index.ts`
re-exports the dispatch registry, the type contract, the injection keys, and any
component a host mounts directly.

**Migration mechanics (for 04-filter-control):**

- `LinkField.vue`'s `import { Link } from "../../Link"` becomes `"../Link"`
  (now one level up).
- `FormLayout/FormLayoutField.vue` and `fieldTypes` consumers import from the new
  module path / `@framework/ui/fields`.
- Update the two tests that reach into `../fields/…`.
- Filter only ever mounts the zero-coupling subset (Check, Select, Link, Date,
  Datetime, Number, Duration, Rating, text); it never provides the form-context
  injections, so the deep-injection components simply stay dormant in Filter
  context — no special handling needed.

## Considered Options

- **Leave `fields/` inside FormLayout; Filter imports across the boundary.**
  Rejected: couples the Filter module to FormLayout's internal folder structure,
  and `fields/` has no export subpath — a host importing it would depend on a
  private path that ADR-0002 says each module should not expose.
- **Move only the value-inputs Filter needs.** Rejected: splits the field set into
  two homes, so FormLayout and Filter would resolve "the Select input" to
  different files — exactly the divergence this consolidation prevents.
