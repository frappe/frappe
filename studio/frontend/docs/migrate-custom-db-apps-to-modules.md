# Migrating Studio database apps

This upgrade converts legacy page scripts to JavaScript modules. Apps remain
stored in the database; exporting them to a repository is optional.

## Automatic changes

During site migration, the converter:

- Wraps a database app's page scripts in `export default function setup(context)`.
- Imports recognized Vue APIs and `call` / `toast` from their libraries.
- Reads referenced page variables, resources, `route`, `router`, and `socket`
  from `context`.
- Returns top-level declarations for use in page bindings and event handlers.
- Moves the legacy app `router_script`, when present, into `router.js`, adding
  imports for `call` and `toast` when used.

Empty scripts and scripts already containing top-level import/export syntax are
skipped. Skipped scripts still need to follow the new format.

## Page-script format

For a page with a resource named `todos`:

```js
import { computed } from "vue"

export default function setup(context) {
	const { todos } = context
	const rows = computed(() => todos.data || [])
	return { rows }
}
```

Page variables remain refs: use `.value` inside scripts. Return state and handlers
that bindings or events need. Put event logic requiring imported APIs inside a
returned handler.

## Manual review

- Database apps can import `vue`, `vue-router`, `pinia`, `frappe-ui`,
  `frappe-ui/list`, `frappe-ui/charts`, and their own files.
- The current converter turns `watchDebounced` into an `@vueuse/core` import,
  which database apps cannot load. Replace it with a Vue watcher and debounce
  logic with cleanup, or export to a repository with that dependency installed.
- Page titles must produce different script filenames within an app. Existing
  conflicting titles are preserved, and nothing reports them: the pages share one
  script path, so one page's script can replace the other's in builds and exports.
  Rename one page and update navigation that uses its title.
- Legacy scripts ran in sloppy mode, so assigning an undeclared name, such as
  `total = 0`, created a global. A module is strict, so the same line now throws
  `ReferenceError: total is not defined`. Declare those names with `const` or `let`.
- Review other implicit helpers, event scripts, and removed component APIs.
  Automatic conversion does not guarantee unchanged behavior for every script.

## Upgrade checks

Back up the site and upgrade a restored staging copy first. Run
`bench --site <site> migrate` after installing the target release. Check every
page, its bindings, actions, navigation, and browser-console errors. Verify
backend methods and permissions with the intended user roles before upgrading
the live site.
