app_name = "frappe"
app_title = "Frappe Framework"
app_publisher = "Web Notes Technologies Pvt. Ltd."
app_description = "Full Stack Web Application Framework in Python"
app_icon = "assets/frappe/images/frappe.svg"
app_version = "4.12.1"
app_color = "#3498db"
app_email = "support@frappe.io"

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

website_clear_cache = "frappe.website.doctype.website_group.website_group.clear_cache"

write_file_keys = ["file_url", "file_name"]

notification_config = "frappe.core.notifications.get_notification_config"

before_tests = "frappe.utils.install.before_tests"

website_generators = ["Web Page", "Blog Post", "Website Group", "Blog Category", "Web Form"]

# permissions

permission_query_conditions = {
	"Event": "frappe.core.doctype.event.event.get_permission_query_conditions",
	"ToDo": "frappe.core.doctype.todo.todo.get_permission_query_conditions",
	"User": "frappe.core.doctype.user.user.get_permission_query_conditions"
}

has_permission = {
	"Event": "frappe.core.doctype.event.event.has_permission",
	"ToDo": "frappe.core.doctype.todo.todo.has_permission",
	"User": "frappe.core.doctype.user.user.has_permission"
}

doc_events = {
	"*": {
		"after_insert": "frappe.core.doctype.email_alert.email_alert.trigger_email_alerts",
		"validate": "frappe.core.doctype.email_alert.email_alert.trigger_email_alerts",
		"on_update": [
			"frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications",
			"frappe.core.doctype.email_alert.email_alert.trigger_email_alerts"
		],
		"after_rename": "frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications",
		"on_submit": "frappe.core.doctype.email_alert.email_alert.trigger_email_alerts",
		"on_cancel": [
			"frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications",
			"frappe.core.doctype.email_alert.email_alert.trigger_email_alerts"
		],
		"on_trash": "frappe.core.doctype.notification_count.notification_count.clear_doctype_notifications"
	},
	"Website Route Permission": {
		"on_update": "frappe.website.doctype.website_group.website_group.clear_cache_on_doc_event"
	}
}

scheduler_events = {
	"all": ["frappe.utils.email_lib.bulk.flush"],
	"daily": [
		"frappe.utils.email_lib.bulk.clear_outbox",
		"frappe.core.doctype.notification_count.notification_count.clear_notifications",
		"frappe.core.doctype.event.event.send_event_digest",
		"frappe.sessions.clear_expired_sessions",
		"frappe.core.doctype.email_alert.email_alert.trigger_daily_alerts",
	],
	"hourly": [
		"frappe.website.doctype.website_group.website_group.clear_event_cache"
	]
}

mail_footer = "frappe.core.doctype.outgoing_email_settings.outgoing_email_settings.get_mail_footer"
