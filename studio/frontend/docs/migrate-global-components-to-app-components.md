# Migrating global components to app components

A Studio Component now belongs to one Studio App when its `studio_app` field is
set. Components exported before this change have no `studio_app`, so they are
global: every app on the site can use them. This guide moves the components of
an exported app into that app.

Do this in the repository of the Frappe app that owns the Studio App. The
migration changes component JSON files only. Page files, script files, file
names, and block trees stay as they are.

## Which components to move

Move every component in
`<frappe_app>/studio/<studio_app>/studio_components/` to the app. An exported
app creates components for its own pages, so they belong to it.

The one exception is a component that another Studio App also uses. That app
has the same component file in its own `studio_components` folder. Keep such a
component global, or give each app its own copy.

A global component cannot use an app's files. Studio rejects a global
component script that imports `@app/` or a relative path, and warns when a
global component contains one of the app's `.vue` components.

## Change each component file

1. Read the app name from the `name` field of
   `<frappe_app>/studio/<studio_app>/<studio_app>.json`. The folder name is the
   scrubbed name (`my-app` is in `my_app`), so do not take the name from the
   folder.
2. In `studio_components/<component_id>.json`, add `studio_app`, change
   `name`, and set `is_standard`:

   ```json
   {
    "component_id": "header",
    "is_standard": 1,
    "name": "helpdesk/header",
    "studio_app": "helpdesk"
   }
   ```

   `name` is `<studio_app>/<component_id>`. Do not change `component_id`, the
   file name, or the script file.

   Some exported components do not have `is_standard` yet. Set it on each
   one, also on a component that stays global. A component without it is
   handled as one made on the site: a site outside developer mode can change
   it, and a patch can rewrite it.
3. Do not change the pages. A block names a component by its `component_id`,
   and the app's own component is used before a global one with the same id.
4. A component inside a moved component must be available too. Move it to the
   app, or keep it global.

## Move input rows to script props

A component now declares what it accepts as `props` in its script. A component
JSON that has `inputs` rows and no script file still works, but the editor can
no longer change the rows. A patch converts the components that were made on
a site. It cannot convert a component of an exported app, because the JSON
file is its source. Convert each one in the same change:

1. Create `studio_components/<component_id>.js` beside the JSON, if the
   component has no script file:

   ```js
   export default {
   	props: {
   		categories: null,
   		columns: { type: Number, default: 3 },
   	},
   }
   ```

2. Write one prop for each row. Use `String`, `Number`, or `Boolean` when the
   row's type is text, number, or checkbox. Use `null` when the value can be
   an array or an object, or when the row's type is not one of these.
3. A row's `default` is text, and the component gets it as a string. Write it
   as a string: `default: "md"`. For a number or a checkbox, write the value of
   that type: `default: 3` or `default: true`. Give an array or object default
   as a function: `default: () => []`. A default with a `{{ }}` binding has no
   equal as a prop default: set the value in `setup`, or on each page that
   uses the component.
4. Remove the `inputs` key from the component JSON.

Blocks in the component still read a value as `{{ inputs.columns }}`, and
pages still set it in `componentProps`. Do not change them. In new blocks, use
`{{ props.columns }}`: `inputs` is the older name of `props`.

## Remove the old global component

The import creates the app component and leaves the old global record in the
database. Other apps on the site still list it. Add a patch to the Frappe app
that deletes each old record:

```python
import frappe
from frappe.studio.sync import sync_studio_apps

COMPONENT_IDS = ["header", "category_grid", "kb_settings"]


def execute():
	sync_studio_apps("helpdesk")
	for component_id in COMPONENT_IDS:
		if frappe.db.exists("Studio Component", component_id):
			frappe.delete_doc("Studio Component", component_id, force=True)
```

Import the app's files first, as the patch does. Studio imports them again at
the end of `bench migrate`, but that is after the patches. On a site in
developer mode, a delete of the global record before the app component exists
also deletes the app's component files.

Do not delete a global component that a database app on a site may use. A
component that the Frappe app shipped under an id specific to the app is safe
to delete. For a generic id such as `header`, check the pages on the sites you
manage first, or keep the global record.

## Checks

1. Run `bench --site <site> migrate` on a development site.
2. Confirm that each moved component exists as `<studio_app>/<component_id>`,
   and that the old `<component_id>` record is gone.
3. Open each page of the app in the editor and in the published app. Check for
   the missing-component placeholder and for console errors.
4. Save one page in developer mode. The component files must stay in place,
   with the new `name` and `studio_app`.
5. Build the app with `bench build --app <frappe_app>`.

## After the migration: remove dependencies on the page

Older components can read a page's variables, data sources, and functions
directly. For example, a component that uses `{{ tasks.data }}` needs the page
to provide `tasks`. It can fail in the component editor or on another page.

New components must receive page data through props and request page actions
through events. Existing components still work, so you can update them
separately from this migration:

1. **Pass page data through props.** For the `tasks` example, declare a
   `tasks` prop in the component script. On each page, set the component
   block's `componentProps.tasks` to `{{ tasks.data }}`. Inside the component,
   change the binding to `{{ props.tasks }}`.
2. **Use events for page actions.** If the component calls a page function
   such as `save()`, declare `"save"` in the component script's `emits`.
   Emit it from the component script with `emit("save")`, using the `emit`
   argument from `setup(props, { emit })`. On each page, handle the event in
   the component block's `componentEvents` and call the page's `save()` there.
3. **Import shared state in app components.** For state used across pages,
   such as the signed-in user, import a composable from the app's files in
   the component script. The component can then get that state without a
   page variable or a prop on every page.

The component can still use values returned by its own `setup()`, slot values
such as `dataItem`, and the built-in `route`, `router`, `socket`, `toast`, and
`call` helpers.

Update one component at a time. Check it in the component editor and on every
page that uses it, including its actions, and check for console errors.
See [Component code](../../../skills/studio-app-building/SKILL.md#component-code)
for the script format.
