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
2. In `studio_components/<component_id>.json`, add `studio_app` and change
   `name`:

   ```json
   {
    "component_id": "header",
    "name": "helpdesk/header",
    "studio_app": "helpdesk"
   }
   ```

   `name` is `<studio_app>/<component_id>`. Do not change `component_id`, the
   file name, or the script file.
3. Do not change the pages. A block names a component by its `component_id`,
   and the app's own component is used before a global one with the same id.
4. A component inside a moved component must be available too. Move it to the
   app, or keep it global.

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
