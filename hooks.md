### List of Hooks

#### Application Name and Details

1. `app_name` - slugified name e.g. "frappe"
1. `app_title` - full title name e.g. "Frappé"
1. `app_publisher`
1. `app_description`
1. `app_version`
1. `app_icon` - font-awesome icon or image url
1. `app_color` - hex colour background of the app icon

#### Install

1. `before_install` - method
1. `after_install` - method


#### Javascript / CSS Builds

1. `app_include_js` - include in "app"
1. `app_include_css` - assets/frappe/css/splash.css

1. `web_include_js` - assets/js/frappe-web.min.js
1. `web_include_css` - assets/css/frappe-web.css

#### Desktop

1. `get_desktop_icons` - method to get list of desktop icons

#### Notifications

1. `notification_config` - method to get notification configuration

#### Permissions

1. `permission_query_conditions:[doctype]` - method to return additional query conditions at time of report / list etc.
1. `has_permission:[doctype]` - method to call permissions to check at individual level
