app_name = "frappe"
app_title = "Frappe Framework"
app_publisher = "Web Notes Technologies Pvt. Ltd. and Contributors"
app_description = "Full Stack Web Application Framwork in Python"
app_icon = "assets/frappe/images/frappe.svg"
app_version = "4.0.0-wip"
app_color = "#3498db"

before_install = "frappe.utils.install.before_install"
after_install = "frappe.utils.install.after_install"

# website
app_include_js = "assets/js/frappe.min.js"
app_include_css = [
		"assets/frappe/css/splash.css",
		"assets/css/frappe.css"
	]
web_include_js = [
		"assets/js/frappe-web.min.js",
		"website_script.js"
	]
web_include_css = [
		"assets/css/frappe-web.css",
		"style_settings.css"
	]

website_clear_cache = "frappe.templates.generators.website_group.clear_cache"

write_file_keys = ["file_url", "file_name"]

notification_config = "frappe.core.notifications.get_notification_config"

before_tests = "frappe.utils.install.before_tests"

# permissions

permission_query_conditions = {
		"Event": "frappe.core.doctype.event.event.get_permission_query_conditions",
		"ToDo": "frappe.core.doctype.todo.todo.get_permission_query_conditions"
	}

has_permission = {
		"Event": "frappe.core.doctype.event.event.has_permission",
		"ToDo": "frappe.core.doctype.todo.todo.has_permission"
	}

# bean

doc_events = {
		"*": {
			"on_update": "frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications",
			"on_cancel": "frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications",
			"on_trash": "frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications"
		},
		"User Vote": {
			"after_insert": "frappe.templates.generators.website_group.clear_cache_on_doc_event"
		},
		"Website Route Permission": {
			"on_update": "frappe.templates.generators.website_group.clear_cache_on_doc_event"
		}
	}

scheduler_events = {
	"all": ["frappe.utils.email_lib.bulk.flush"],
	"daily": [
		"frappe.utils.email_lib.bulk.clear_outbox",
		"frappe.core.doctype.notification_count.notification_count.delete_event_notification_count",
		"frappe.core.doctype.event.event.send_event_digest",
	],
	"hourly": [
		"frappe.templates.generators.website_group.clear_event_cache"
	]
}
