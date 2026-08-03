# Filter control ports CRM's Filter onto shared value-inputs, not frappe-ui ListFilter

The **Filter** control is built in `@framework/ui` by porting CRM's `Filter.vue`
logic and **data model** — a list of conditions `{ field, fieldname, operator,
value }` — rather than wrapping frappe-ui's `ListFilter`. Field Options come from
`useDoctypeMeta` (per [ADR-0001](0001-listview-controls-are-controlled-meta-driven.md)),
replacing CRM's `crm.api.doc.get_filterable_fields`. The per-fieldtype **operator**
table (CRM's `getOperators`: strings get equals/like/in/is…, Date gets the full
nine incl. `between`/`timespan`, Check gets equals only, plus the `_assign`
special case) is extracted as a pure, frappe-ui-free `.ts` so it is unit-testable.
The popover reuses a frappe-ui primitive for positioning — frappe-ui's
`NestedPopover` (self-contained Popper wrapper) or `Popover` — so we don't
re-derive positioning. The fieldtype-aware **value inputs** are the shared `Fields`
module's components ([ADR-0004](0004-fields-relocated-to-shared-module.md)), not
CRM's bespoke Link/Duration/Rating trio and not frappe-ui `FormControl`.

This keeps Filter a **controlled component** (`v-model` ↔ a `Filter[]` list, plus
`doctype`), reaches feature/pixel parity with CRM's popover, and dogfoods the
shared value inputs. The few gaps the shared inputs don't yet cover (Date
`between` → range, `is`/`is not` → Set/Not-Set select, `timespan` presets) are
operator-driven input swaps handled in the Filter `.vue`, not new field
components.

The **wire form** (`serializeFilters` / `parseFilters`) is Frappe's list of
`[fieldname, operator, value]` triples — **not** CRM's fieldname-keyed dict
(`parseFilters` in CRM's `Filter.vue`). This is a deliberate divergence: the same
reason the dict-modeled `ListFilter` was rejected below (a dict can't hold one
field filtered twice, e.g. `amount > 100 AND amount < 500`) applies equally to
CRM's serialization, so the list form is the only shape consistent with the
control's `Filter[]` model. Hosts pass the list straight to a Frappe `get_list`
filters argument.

## Considered Options

- **Wrap frappe-ui `ListFilter` (295 lines).** Rejected: its dict model
  `{ fieldname: [operator, value] }` structurally cannot hold the same field
  filtered twice (e.g. `amount > 10 AND amount < 100`), and it ships only 2–4
  operators per type with select/Link/text inputs only — a feature downgrade that
  fails the pixel/feature-parity acceptance criterion.
- **Verbatim fork CRM's `Filter.vue` (717 lines), custom controls and all.**
  Rejected: drags CRM's bespoke `Link`/`DurationInput`/`RatingInput` into the
  library as duplicates of the `Fields` value-inputs, so nothing is dogfooded and
  two homes for value inputs diverge.
- **Keep CRM's `get_filterable_fields` endpoint.** Rejected by ADR-0001: couples
  the library to CRM's data shape; derive Field Options from Meta instead.
