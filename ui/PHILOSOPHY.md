# @framework/ui — Design Philosophy

This is the rulebook that governs component design across `@framework/ui`. Every
principle is **generative**: applying it gives you the right answer in situations it
doesn't explicitly cover. When two principles tug in opposite directions, the
principle text usually points at the tiebreaker.

**Audience:** contributors, AI agents doing PRs, reviewers. Not end users.

**How to use it:**

- Cite by ID in PRs and issues (`"this violates FP1"`, `"FP2 host-owns-persistence applies"`).
- When you draft a new component or refactor an old one, walk this doc top-to-bottom.
- When a principle stops being generative — when it forces a clearly wrong answer in a
  real case — propose an edit, don't carve a quiet exception.

**Relationship to other docs:**

- **`@framework/ui` inherits `frappe-ui`'s PHILOSOPHY (`P1`–`P14`) in full.**
  Every component here composes frappe-ui atoms, so frappe-ui's rules on naming (P1),
  v-model (P2), primitive props (P3), color axes (P4), labeling (P5), slot vocabulary
  (P6/P7), splitting (P8), styling via data-\* (P10), icons (P11), a11y (P12), and
  deprecation (P13) already apply. This doc does **not** restate them — it adds only the
  `FP*` principles specific to `@framework/ui`. Two divergent copies of `P1`–`P14` is
  exactly the drift these rules exist to prevent.
  The canonical rulebook is **[frappe-ui's `PHILOSOPHY.md`](https://github.com/frappe/frappe-ui/blob/main/PHILOSOPHY.md)**.
  We link the upstream source rather than a local path on purpose: `frappe-ui` is a peer
  dependency each consuming app vendors at a different location (a bench app's
  `node_modules/frappe-ui`, a submodule, …), and it is not shipped in the package's `files`,
  so no relative or package-relative path resolves everywhere. The GitHub URL is the one
  stable reference.
- **`CONTEXT.md`** is the *vocabulary*: what a **Sort**, **Filter**, **Column**,
  **Controlled component**, **View Snapshot** mean. PHILOSOPHY is the *rules* that use
  the vocabulary.
- **`docs/adr/`** are *decisions* — specific applications of principles to specific
  questions (e.g. ADR-0007, persistence deferred to the host). ADRs cite principles;
  principles don't cite ADRs.

---

## Composition

### FP1. Compose frappe-ui atoms; don't rebuild them

**Rule:** Before hand-rolling any UI element, use the `frappe-ui` equivalent (`Dialog`,
`Button`, `Select`, `TextInput`, `Switch`, `Tabs`, `TabButtons`, `ErrorMessage`, …).
`@framework/ui` is a slim library of *higher-level, Frappe-integrated* components — its
job is to compose atoms into doctype-aware controls, not to reimplement the atoms. When
no frappe-ui equivalent exists and you build a custom element, leave a comment noting the
gap, so the custom code reads as a deliberate fallback rather than a missed reuse.

**Why:** The atoms already ship the ARIA, keyboard nav, focus management, and theming
baseline (frappe-ui P12). Rebuilding them duplicates that surface, drifts from it, and
loses the fixes upstream makes. See `CLAUDE.md` for the operational frappe-ui vs
`@framework/ui` disambiguation.

---

### FP2. List-view controls are controlled components — the host owns fetching and persistence

**Rule:** A control (SortBy, Filter, Column Settings, Quick Filter, …) owns exactly one
slice of view state via `v-model` plus a `doctype`, emits changes, and **never** touches a
data-fetching resource or a persistence layer. The host wires fetching, cross-control
sync, and *when/where* to save. The library tops out at a serializable **View Snapshot**
and never owns a saved View entity.

**Why:** Keeping controls stateless-of-IO makes them reusable across apps with different
data and persistence models, and keeps CRM's "Views" concept out of the shared library.
See `CONTEXT.md` (**Controlled component**, **View Snapshot**) and
[ADR-0007](docs/adr/0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md).

---

### FP3. Derive options from doctype Meta, not from app-specific endpoints

**Rule:** The fields a control offers (sortable fields, filterable fields, column
candidates) are derived **client-side from doctype Meta** (via the shared
`useDoctypeMeta`), not fetched from a consuming app's bespoke endpoint (`sort_options`,
`filterable_fields`, …).

**Why:** Meta is the one source every Frappe app already has; deriving from it keeps the
controls app-agnostic and avoids coupling the shared library to any one app's API surface.
See `CONTEXT.md` (**Field Options**, **Meta**).

