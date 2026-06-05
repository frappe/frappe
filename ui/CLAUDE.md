# `@framework/ui` — working notes

Shared client components for Frappe apps (`src/index.ts` is the only entry;
`package.json` ships `src/` as-is, no build step). `frappe-ui`, `vue`, and
`vue-router` are **peer deps** — this package does **not** install them.

## Testing — read this before adding or running tests

This package has **no test tooling of its own**: no `vitest` config, no
`@vitejs/plugin-vue`, no DOM env, and (being source-only with peer deps) **no
`frappe-ui` / `vue` installed in its own `node_modules`**. Frappe does not provide
a vitest harness for it. So there are two tiers of tests, and only one runs
standalone:

### Pure-TS tests — run standalone (preferred)

Tests that import **only `.ts`** (no `.vue`, no `frappe-ui`) run directly with an
ephemeral vitest, from this directory (`apps/frappe/ui`):

```bash
npx vitest run src/components/FormLayout/tests/<file>.test.ts
# or the whole pure-TS suite:
npx vitest run src/components/FormLayout/tests/{resolveLayout,dependsOn,buildLayoutFromMeta,useDoctypeLayout,formatNumber,formatDefaults,scopedRegistry}.test.ts
```

Verified working (vitest 4.x). These need no vue plugin and no DOM. **Design new
unit tests to stay in this tier** — test pure modules (`buildLayoutFromMeta`,
`resolveLayout`, `dependsOn`, `formatNumber`, `formatDefaults`, `scopedRegistry`,
`useDoctypeLayout`) rather than mounting `.vue` components. This is why the
FormLayout architecture pushes logic into pure `.ts` seams and keeps `.vue` files
thin — e.g. `registerFieldType`'s `{ global: false }` snapshot/restore lives in
the pure `scopedRegistry.ts` (driven by Vue's `effectScope`), not in the `.vue`.

### `.vue` / `frappe-ui`-importing tests — need a host app harness

`tests/fieldTypes.test.ts` imports the field `.vue` SFCs (which import
`frappe-ui`). Running it standalone fails in stages:

1. without a vue plugin → "Install @vitejs/plugin-vue to handle .vue files";
2. with a borrowed plugin → `frappe-ui` is unresolved here;
3. aliasing `frappe-ui` to a sibling app's copy → its `src` has extensionless
   imports that only resolve under that app's full vite config.

So these tests are runnable only inside a **consuming app's** vitest/vite setup
(e.g. `apps/crm/frappe-ui` or `apps/crm/frontend`, which have `@vitejs/plugin-vue`
+ `frappe-ui` + a DOM env). Don't try to wire a standalone config for them — keep
component-mounting tests in the app that consumes this package. `fieldTypes.test`
only asserts registry identity (fieldtype → component object), which the pure-TS
registry logic already covers conceptually; treat its red standalone run as
expected, not a regression you introduced.

## FormLayout component

The big work-in-progress here is `src/components/FormLayout/` — a generic,
app-agnostic doc-form renderer (replacing CRM's welded `FieldLayout`). Its design
lives in `src/components/FormLayout/plans/` (cross-phase `PLAN.md` + per-phase
folders). **That `plans/` folder is local scratch — never `git add` it.** Commit
only code.

Key locked decisions (see `plans/PLAN.md`): `FormLayout` is **render-only**
(takes a ready `layout` schema, never fetches meta); schema production is a
separate seam (`useDoctypeLayout` → `buildLayoutFromMeta`); fieldtype → component
is a **registry** (`registerFieldType`) that apps override — this registry is the
**only** extension seam (no behaviour props, no root-`provide`, no events on
`FormLayout`). App-specific behaviour and site settings reach a field by the app
**registering its own field component** that imports its own deps / reads its own
settings source.
