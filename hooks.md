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
1. `awesomebar_search` - method(txt) returning extra Awesome Bar results (`label`, `description`, `route`, `index`)

#### Notifications

1. `notification_config` - method to get notification configuration

#### Permissions

1. `permission_query_conditions:[doctype]` - method to return additional query conditions at time of report / list etc.
1. `has_permission:[doctype]` - method to call permissions to check at individual level
