### List of Hooks

#### Application Name and Details

1. `app_name` - slugified name e.g. "frappe"
1. `app_title` - full title name e.g. "Frappe"
1. `app_publisher`
1. `app_description`
1. `app_version`

#### Install

1. `before_install` - method
1. `after_install` - method

#### Disable / Enable

The site runs these hooks when it disables an app, and when it enables the app again. The app keeps its schema and its data. These hooks change only what the app does on the site.

1. `before_disable` - method, runs while the app is still active
2. `after_disable` - method, runs after the app becomes inactive
3. `before_enable` - method, runs while the app is still inactive
4. `after_enable` - method, runs after the app becomes active again

An app hides and shows its own customizations in these hooks. Call `frappe.custom.hide_customizations` from `before_disable`, and `frappe.custom.unhide_customizations` from `after_enable`. `bench migrate` runs `before_disable` again, so `before_disable` must give the same result each time.

A disable or an enable is one transaction. If a hook fails, the site keeps the state that it had before, and nothing the hook wrote remains.

#### Javascript / CSS Builds

1. `app_include_js` - include in "app"
1. `app_include_css` - assets/frappe/css/splash.css

1. `web_include_js` - assets/js/frappe-web.min.js
1. `web_include_css` - assets/css/frappe-web.css

#### Desktop

1. `get_desktop_icons` - method to get list of desktop icons
1. `awesomebar_search` - method(txt) returning extra Awesome Bar results (`label`, `description`, `route`, `index`). `route` may be a desk route list, an in-app path (`/desk/...`), or an `http(s)://` URL.
1. `add_to_apps_screen` - list of dicts, one per app to place on the apps screen
1. `add_to_dock` - ordered list of dicts, one per entry, stating where an app's entries sit on the dock

#### Navigation an app ships

A sidebar belongs to a **module**. An app ships one `Sidebar` per module at
`<app>/<module>/sidebar/<module>/<module>.json`, exported by turning on `standard` in
developer mode. A module whose app ships none is not without navigation: its sidebar is
computed from what the module contains — its workspaces, doctypes, reports, dashboards and
pages — and stays in step with them.

Two folders an app used to ship are no longer read:

- **`<app>/workspace_sidebar/*.json`** — the flat, app-level sidebar fixtures. These stop
  being imported. Convert them with

  ```bash
  bench --site <site> convert-sidebar-fixtures --app <app>
  ```

  which merges each module's fixtures into one per-module export and writes it where the
  ordinary doc-files walk will find it. It never overwrites a file that is already there, so
  it is safe to run against an app part-way through converting by hand, and `--dry-run`
  reports without writing. The old folder is left alone; delete it once you are happy with the
  result. Until an app converts, its modules fall back to computed sidebars.

- **`<app>/desktop_icon/*.json`** — the icon-grid fixtures. These are still imported, but only
  onto a site that has chosen the icon grid, and the grid is being retired. Use
  `add_to_apps_screen` to place an app on the apps screen, and `add_to_dock` to state where its
  entries sit on the dock.

#### The dock an app ships

The dock (the rail down the left of the desk) lists an app's modules, and `add_to_dock` is where
an app states the order they appear in. It is an ordered **list of dicts**, each a typed row —
never a map, and there is no fixture behind it:

```python
# <app>/hooks.py
add_to_dock = [
	{"type": "Sidebar", "name": "Stock"},
	{"type": "Sidebar", "name": "Accounts"},
	{"type": "Sidebar", "name": "Assets", "hidden": 1},
]
```

`type` is `Sidebar` (a module — a sidebar's name is its module's name) or `Workspace`. An entry
the list never names simply trails the ones it does, in the app's own order, so adding a module
later does not mean re-authoring the block. A row shipped `hidden` is off by default; a site or a
person can bring it back with one drag in the dock manager.

The site's arrangement and each person's own are laid over this, and they only order and hide —
they never add.

A **companion app** — one that extends a host app rather than standing on its own — pins a
workspace onto the host's dock with the same hook, by naming the host in `app`:

```python
# india_compliance/hooks.py
add_to_dock = [
	{"type": "Workspace", "name": "GST", "app": "erpnext"},
]
```

The pin is appended after the host's own entries rather than positioned among them, and it is
permission-checked like any other workspace. Declaring one keeps the companion off the apps
screen — pinning into a host costs the slot, so it takes precedence over `add_to_apps_screen`.
Declaring your *own* order costs nothing. A companion whose other workspaces should also keep the
host's dock on screen declares `app_rail_host` as well.

#### Notifications

1. `notification_config` - method to get notification configuration

#### Permissions

1. `permission_query_conditions:[doctype]` - method to return additional query conditions at time of report / list etc.
1. `has_permission:[doctype]` - method to call permissions to check at individual level
