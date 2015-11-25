from __future__ import unicode_literals
app_name = "frappe"
app_title = "Frappe Framework"
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "Full stack web framework with Python, Javascript, MariaDB, Redis, Node"

app_icon = "octicon octicon-circuit-board"
app_version = "6.9.3"
app_color = "orange"
source_link = "https://github.com/frappe/frappe"
app_license = "MIT"

app_email = "info@frappe.io"

before_install = "frappe.utils.install.before_install"
after_install = "frappe.utils.install.after_install"

# website
app_include_js = [
	"assets/js/desk.min.js",
	"assets/js/editor.min.js",
	"assets/js/list.min.js",
	"assets/js/form.min.js",
	"assets/js/report.min.js",
	"assets/js/module.min.js"
]
app_include_css = [
	"assets/css/desk.min.css",
	"assets/css/list.min.css",
	"assets/css/form.min.css",
	"assets/css/report.min.css",
	"assets/css/module.min.css"
]

web_include_js = [
	"website_script.js"
]

bootstrap = "assets/frappe/css/bootstrap.css"
web_include_css = [
	"assets/css/frappe-web.css"
]
website_route_rules = [
	{"from_route": "/blog", "to_route": "Blog Post"},
	{"from_route": "/blog/<category>", "to_route": "Blog Post"}
]

website_context = {
	"hero": {
		"blog": "templates/includes/blog/hero.html"
	}
}

write_file_keys = ["file_url", "file_name"]

notification_config = "frappe.core.notifications.get_notification_config"

before_tests = "frappe.utils.install.before_tests"

website_generators = ["Web Page", "Blog Post", "Blog Category", "Web Form"]

email_append_to = ["Event", "ToDo", "Communication"]

calendars = ["Event"]

# login

on_session_creation = [
	"frappe.desk.doctype.feed.feed.login_feed",
	"frappe.core.doctype.user.user.notifify_admin_access_to_system_manager"
]

# permissions

permission_query_conditions = {
	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
	"ToDo": "frappe.desk.doctype.todo.todo.get_permission_query_conditions",
	"User": "frappe.core.doctype.user.user.get_permission_query_conditions",
	"Feed": "frappe.desk.doctype.feed.feed.get_permission_query_conditions",
	"Note": "frappe.desk.doctype.note.note.get_permission_query_conditions"
}

has_permission = {
	"Event": "frappe.desk.doctype.event.event.has_permission",
	"ToDo": "frappe.desk.doctype.todo.todo.has_permission",
	"User": "frappe.core.doctype.user.user.has_permission",
	"Feed": "frappe.desk.doctype.feed.feed.has_permission",
	"Note": "frappe.desk.doctype.note.note.has_permission"
}

standard_queries = {
	"User": "frappe.core.doctype.user.user.user_query"
}

doc_events = {
	"*": {
		"after_insert": "frappe.email.doctype.email_alert.email_alert.trigger_email_alerts",
		"validate": "frappe.email.doctype.email_alert.email_alert.trigger_email_alerts",
		"on_update": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.email.doctype.email_alert.email_alert.trigger_email_alerts",
			"frappe.desk.doctype.feed.feed.update_feed"
		],
		"after_rename": "frappe.desk.notifications.clear_doctype_notifications",
		"on_submit": [
			"frappe.email.doctype.email_alert.email_alert.trigger_email_alerts",
			"frappe.desk.doctype.feed.feed.update_feed"
		],
		"on_cancel": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.email.doctype.email_alert.email_alert.trigger_email_alerts"
		],
		"on_trash": "frappe.desk.notifications.clear_doctype_notifications"
	}
}

scheduler_events = {
	"all": [
		"frappe.email.bulk.flush",
		"frappe.email.doctype.email_account.email_account.pull",
		"frappe.email.doctype.email_account.email_account.notify_unreplied",
	],
	"daily": [
		"frappe.email.bulk.clear_outbox",
		"frappe.desk.notifications.clear_notifications",
		"frappe.core.doctype.scheduler_log.scheduler_log.set_old_logs_as_seen",
		"frappe.desk.doctype.event.event.send_event_digest",
		"frappe.sessions.clear_expired_sessions",
		"frappe.email.doctype.email_alert.email_alert.trigger_daily_alerts",
		"frappe.async.remove_old_task_logs",
	],
	"daily_long": [
		"frappe.integrations.doctype.dropbox_backup.dropbox_backup.take_backups_daily"
	],
	"weekly_long": [
		"frappe.integrations.doctype.dropbox_backup.dropbox_backup.take_backups_weekly"
	]

}

default_background = "/assets/frappe/images/ui/into-the-dawn.jpg"

get_translated_dict = {
	("doctype", "System Settings"): "frappe.geo.country_info.get_translated_dict",
	("page", "setup-wizard"): "frappe.geo.country_info.get_translated_dict"
}

sounds = [
	{"name": "email", "src": "/assets/frappe/sounds/email.mp3"},
	{"name": "submit", "src": "/assets/frappe/sounds/submit.mp3"},
	{"name": "cancel", "src": "/assets/frappe/sounds/cancel.mp3"},
	{"name": "delete", "src": "/assets/frappe/sounds/delete.mp3"},
	{"name": "click", "src": "/assets/frappe/sounds/click.mp3"},
	{"name": "error", "src": "/assets/frappe/sounds/error.mp3"},
	# {"name": "alert", "src": "/assets/frappe/sounds/alert.mp3"},
	# {"name": "chime", "src": "/assets/frappe/sounds/chime.mp3"},
]
