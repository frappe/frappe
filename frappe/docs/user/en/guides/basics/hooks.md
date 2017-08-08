# Hooks
<!-- TODO: Add tables for quick reference -->

Hooks are the duct tape of the Frappé system. Hooks allow you to "hook" in to
functionality and events of other parts of the Frappé system. Following are the
official hooks from Frappé. 

### Application Name and Details

1. `app_name` - slugified name with underscores e.g. "shopping\_cart"
2. `app_title` - full title name e.g. "Frappé"
3. `app_publisher`
4. `app_description`
5. `app_version`
6. `app_icon` - font-awesome icon or image url
7. `app_color` - hex colour background of the app icon

### Install Events

1. `before_install`
2. `after_install`

The above hooks are called before and after installation of the app they are in.
For example, [ERPNext](/apps/erpnext)'s hooks contains a line,

	after_install = "erpnext.setup.install.after_install"

So, the function after\_install is imported and called after ERPNext is installed.

Note, the `before_install` and `after_install` hooks are called with no arguments.

### Boot Session

After a successful login, the Frappé JS Client requests for a resource called
`bootinfo`. The `bootinfo` is available as a global in Javascript via
`frappe.boot`. By default, the `bootinfo` contains

* System defaults
* Notification status
* Permissions
* List of icons on desktop
* User settings
* Language and timezone info

If your app wants to modify bootinfo, it can declare a hook `boot_session`. The
value is assumed to be a dotted path to a function and is called with one
argument, bootinfo which it can modify and return.

Eg,

	boot_session = "erpnext.startup.boot.boot_session"

### Notification configurations

The notification configuration hook is expected to return a Python dictionary.

	{ 
		"for_doctype": {
			"Issue": {"status":"Open"},
			"Customer Issue": {"status":"Open"},
		},
		"for_module_doctypes": {
			"ToDo": "To Do",
			"Event": "Calendar",
			"Comment": "Messages"
		},
		"for_module": {
			"To Do": "frappe.core.notifications.get_things_todo",
			"Calendar": "frappe.core.notifications.get_todays_events",
			"Messages": "frappe.core.notifications.get_unread_messages"
		}
	}


The above configuration has three parts,

1. `for_doctype` part of the above configuration marks any "Issue"
	or "Customer Issue" as unread if its status is Open
2. `for_module_doctypes` maps doctypes to module's unread count.
3. `for_module` maps modules to functions to obtain its unread count. The
   functions are called without any argument.

### Javascript / CSS Assets

The following hooks allow you to bundle built assets to your app for serving.
There are two types of assets, app and web. The app assets are loaded in the
Desk and web assets are loaded in the website.

1. `app_include_js`
2. `app_include_css`
3. `web_include_js`
4. `web_include_css`

Eg,

	app_include_js = "assets/js/erpnext.min.js"
	web_include_js = "assets/js/erpnext-web.min.js"

Note: to create an asset bundle (eg, assets/js/erpnext.min.js) the target file
should be in build.json of your app.

### Configuring Reports

In the report view, you can force filters as per doctype using `dump_report_map`
hook. The hook should be a dotted path to a Python function which will be called
without any arguments. Example of output of this function is below.


	"Warehouse": {
		"columns": ["name"],
		"conditions": ["docstatus < 2"],
		"order_by": "name"
	}

Here, for a report with Warehouse doctype, would include only those records that
are not cancelled (docstatus < 2) and will be ordered by name.

### Modifying Website Context

Context used in website pages can be modified by adding
a `update_website_context` hook. This hook should be a dotted path to a function
which will be called with a context (dictionary) argument.

### Customizing Email footer

By default, for every email, a footer with content, "Sent via Frappé" is sent.
You can customize this globally by adding a `mail_footer` hook. The hook should
be a dotted path to a variable.

### Session Creation Hook

You can attach custom logic to the event of a successful login using
`on_session_creation` hook. The hook should be a dotted path to a Python
function that takes login\_manager as an argument.

Eg,

	def on_session_creation(login_manager):
		"""make feed"""
		if frappe.session['user'] != 'Guest':
			# log to timesheet
			pass

### Website Clear Cache

If you cache values in your views, the `website_clear_cache` allows you to hook
methods that invalidate your caches when Frappé tries to clear cache for all
website related pages.

### Document hooks

#### Permissions

#### Query Permissions
You can customize how permissions are resolved for a DocType by hooking custom
permission match conditions using the `permission_query_conditions` hook. This
match condition is expected to be fragment for a where clause in an sql query.
Structure for this hook is as follows.


	permission_query_conditions = {
		"{doctype}": "{dotted.path.to.function}",
	}

The output of the function should be a string with a match condition.
Example of such a function,


	def get_permission_query_conditions():
		return "(tabevent.event_type='public' or tabevent.owner='{user}'".format(user=frappe.session.user)

The above function returns a fragment that permits an event to listed if it's
public or owned by the current user.

#### Document permissions
You can hook to `doc.has_permission` for any DocType and add special permission
checking logic using the `has_permission` hook. Structure for this hook is,

	has_permission = {
		"{doctype}": "{dotted.path.to.function}",
	}

The function will be passed the concerned document as an argument. It should
True or a falsy value after running the required logic. 

For Example,

	def has_permission(doc):
		if doc.event_type=="Public" or doc.owner==frappe.session.user:
			return True

The above function permits an event if it's public or owned by the current user.

#### CRUD Events

You can hook to various CRUD events of any doctype, the syntax for such a hook
is as follows,

	doc_events = {
		"{doctype}": {
			"{event}": "{dotted.path.to.function}",
		}
	}

To hook to events of all doctypes, you can use the follwing syntax also,

	 doc_events = {
	 	"*": {
	 		"on_update": "{dotted.path.to.function}",
		}
	 }

The hook function will be passed the doc in concern as the only argument.

##### List of events

* `validate`
* `before_save`
* `autoname`
* `after_save`
* `before_insert`
* `after_insert`
* `before_submit`
* `before_cancel`
* `before_update_after_submit`
* `on_update`
* `on_submit`
* `on_cancel`
* `on_update_after_submit`
* `on_change`
* `on_trash`
* `after_delete`


Eg, 

	doc_events = {
		"Cab Request": {
			"after_insert": topcab.schedule_cab",
		}
	}

### Scheduler Hooks

Scheduler hooks are methods that are run periodically in background. Structure for such a hook is,

	scheduler_events = {
		"{event_name}": [
			"{dotted.path.to.function}"
		],
	}

#### Events

* `daily`
* `daily_long`
* `weekly`
* `weekly_long`
* `monthly`
* `monthly_long`
* `hourly`
* `all`

The scheduler events require celery, celerybeat and redis (or a supported and
configured broker) to be running. The events with suffix '\_long' are for long
jobs. The `all` event is triggered everytime (as per the celerybeat interval).

Example,

	scheduler_events = {
		"{daily}": [
			"erpnext.accounts.doctype.sales_invoice.sales_invoice.manage_recurring_invoices"
		],
		"{daily_long}": [
			"erpnext.setup.doctype.backup_manager.backup_manager.take_backups_daily"
		],
	}
