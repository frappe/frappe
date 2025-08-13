import os

from . import __version__ as app_version

app_name = "frappe"
app_title = "Frappe Framework"
app_publisher = "Frappe Technologies"
app_description = "Full stack web framework with Python, Javascript, MariaDB, Redis, Node"
app_license = "MIT"
app_logo_url = "/assets/frappe/images/frappe-framework-logo.svg"
develop_version = "15.x.x-develop"
app_home = "/app/build"

app_email = "developers@frappe.io"

before_install = "frappe.utils.install.before_install"
after_install = "frappe.utils.install.after_install"

page_js = {"setup-wizard": "public/js/frappe/setup_wizard.js"}

# website
app_include_js = [
	"libs.bundle.js",
	"desk.bundle.js",
	"list.bundle.js",
	"form.bundle.js",
	"controls.bundle.js",
	"report.bundle.js",
	"telemetry.bundle.js",
	"billing.bundle.js",
]

app_include_css = [
	"desk.bundle.css",
	"report.bundle.css",
]
app_include_icons = [
	"/assets/frappe/icons/timeless/icons.svg",
	"/assets/frappe/icons/espresso/icons.svg",
]

doctype_js = {
	"Web Page": "public/js/frappe/utils/web_template.js",
	"Website Settings": "public/js/frappe/utils/web_template.js",
}

web_include_js = ["website_script.js"]
web_include_css = []
web_include_icons = [
	"/assets/frappe/icons/timeless/icons.svg",
	"/assets/frappe/icons/espresso/icons.svg",
]

email_css = ["email.bundle.css"]

website_route_rules = [
	{"from_route": "/kb/<category>", "to_route": "Help Article"},
	{"from_route": "/profile", "to_route": "me"},
	{"from_route": "/app/<path:app_path>", "to_route": "app"},
]

website_redirects = [
	{"source": r"/desk(.*)", "target": r"/app\1"},
]

base_template = "templates/base.html"

write_file_keys = ["file_url", "file_name"]

notification_config = "frappe.core.notifications.get_notification_config"

before_tests = "frappe.utils.install.before_tests"

email_append_to = ["Event", "ToDo", "Communication"]

calendars = ["Event"]

# login

on_session_creation = [
	"frappe.core.doctype.activity_log.feed.login_feed",
	"frappe.core.doctype.user.user.notify_admin_access_to_system_manager",
]

on_login = "frappe.desk.doctype.note.note._get_unseen_notes"
on_logout = "frappe.core.doctype.session_default_settings.session_default_settings.clear_session_defaults"

# PDF
pdf_header_html = "frappe.utils.pdf.pdf_header_html"
pdf_body_html = "frappe.utils.pdf.pdf_body_html"
pdf_footer_html = "frappe.utils.pdf.pdf_footer_html"

# permissions

permission_query_conditions = {
	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
	"ToDo": "frappe.desk.doctype.todo.todo.get_permission_query_conditions",
	"User": "frappe.core.doctype.user.user.get_permission_query_conditions",
	"Dashboard Settings": "frappe.desk.doctype.dashboard_settings.dashboard_settings.get_permission_query_conditions",
	"Notification Log": "frappe.desk.doctype.notification_log.notification_log.get_permission_query_conditions",
	"Dashboard": "frappe.desk.doctype.dashboard.dashboard.get_permission_query_conditions",
	"Dashboard Chart": "frappe.desk.doctype.dashboard_chart.dashboard_chart.get_permission_query_conditions",
	"Number Card": "frappe.desk.doctype.number_card.number_card.get_permission_query_conditions",
	"Notification Settings": "frappe.desk.doctype.notification_settings.notification_settings.get_permission_query_conditions",
	"Note": "frappe.desk.doctype.note.note.get_permission_query_conditions",
	"Kanban Board": "frappe.desk.doctype.kanban_board.kanban_board.get_permission_query_conditions",
	"Contact": "frappe.contacts.address_and_contact.get_permission_query_conditions_for_contact",
	"Address": "frappe.contacts.address_and_contact.get_permission_query_conditions_for_address",
	"Communication": "frappe.core.doctype.communication.communication.get_permission_query_conditions_for_communication",
	"Workflow Action": "frappe.workflow.doctype.workflow_action.workflow_action.get_permission_query_conditions",
	"Prepared Report": "frappe.core.doctype.prepared_report.prepared_report.get_permission_query_condition",
	"File": "frappe.core.doctype.file.file.get_permission_query_conditions",
	"User Invitation": "frappe.core.doctype.user_invitation.user_invitation.get_permission_query_conditions",
}

has_permission = {
	"Event": "frappe.desk.doctype.event.event.has_permission",
	"ToDo": "frappe.desk.doctype.todo.todo.has_permission",
	"Note": "frappe.desk.doctype.note.note.has_permission",
	"User": "frappe.core.doctype.user.user.has_permission",
	"Dashboard Chart": "frappe.desk.doctype.dashboard_chart.dashboard_chart.has_permission",
	"Number Card": "frappe.desk.doctype.number_card.number_card.has_permission",
	"Kanban Board": "frappe.desk.doctype.kanban_board.kanban_board.has_permission",
	"Contact": "frappe.contacts.address_and_contact.has_permission",
	"Address": "frappe.contacts.address_and_contact.has_permission",
	"Communication": "frappe.core.doctype.communication.communication.has_permission",
	"Workflow Action": "frappe.workflow.doctype.workflow_action.workflow_action.has_permission",
	"File": "frappe.core.doctype.file.file.has_permission",
	"Prepared Report": "frappe.core.doctype.prepared_report.prepared_report.has_permission",
	"Notification Settings": "frappe.desk.doctype.notification_settings.notification_settings.has_permission",
	"User Invitation": "frappe.core.doctype.user_invitation.user_invitation.has_permission",
}

has_website_permission = {"Address": "frappe.contacts.doctype.address.address.has_website_permission"}

jinja = {
	"methods": "frappe.utils.jinja_globals",
	"filters": [
		"frappe.utils.data.global_date_format",
		"frappe.utils.markdown",
		"frappe.website.utils.abs_url",
	],
}

standard_queries = {"User": "frappe.core.doctype.user.user.user_query"}

doc_events = {
	"*": {
		"on_update": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.core.doctype.file.utils.attach_files_to_document",
			"frappe.automation.doctype.assignment_rule.assignment_rule.apply",
			"frappe.automation.doctype.assignment_rule.assignment_rule.update_due_date",
			"frappe.core.doctype.user_type.user_type.apply_permissions_for_non_standard_user_type",
			"frappe.core.doctype.permission_log.permission_log.make_perm_log",
			"frappe.search.sqlite_search.update_doc_index",
		],
		"after_rename": "frappe.desk.notifications.clear_doctype_notifications",
		"on_cancel": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.automation.doctype.assignment_rule.assignment_rule.apply",
		],
		"on_trash": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.search.sqlite_search.delete_doc_index",
		],
		"on_update_after_submit": [
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.automation.doctype.assignment_rule.assignment_rule.apply",
			"frappe.automation.doctype.assignment_rule.assignment_rule.update_due_date",
			"frappe.core.doctype.file.utils.attach_files_to_document",
		],
		"on_change": [
			"frappe.automation.doctype.milestone_tracker.milestone_tracker.evaluate_milestone",
		],
		"after_delete": ["frappe.core.doctype.permission_log.permission_log.make_perm_log"],
	},
	"Event": {
		"after_insert": "frappe.integrations.doctype.google_calendar.google_calendar.insert_event_in_google_calendar",
		"on_update": "frappe.integrations.doctype.google_calendar.google_calendar.update_event_in_google_calendar",
		"on_trash": "frappe.integrations.doctype.google_calendar.google_calendar.delete_event_from_google_calendar",
	},
	"Contact": {
		"after_insert": "frappe.integrations.doctype.google_contacts.google_contacts.insert_contacts_to_google_contacts",
		"on_update": "frappe.integrations.doctype.google_contacts.google_contacts.update_contacts_to_google_contacts",
	},
	"DocType": {
		"on_update": "frappe.cache_manager.build_domain_restricted_doctype_cache",
	},
	"Page": {
		"on_update": "frappe.cache_manager.build_domain_restricted_page_cache",
	},
}

scheduler_events = {
	"cron": {
		# 5 minutes
		"0/5 * * * *": [
			"frappe.email.doctype.notification.notification.trigger_offset_alerts",
		],
		# 15 minutes
		"0/15 * * * *": [
			"frappe.email.doctype.email_account.email_account.notify_unreplied",
			"frappe.utils.global_search.sync_global_search",
			"frappe.deferred_insert.save_to_db",
			"frappe.automation.doctype.reminder.reminder.send_reminders",
			"frappe.model.utils.link_count.update_link_count",
			"frappe.search.sqlite_search.build_index_if_not_exists",
		],
		# 10 minutes
		"0/10 * * * *": [
			"frappe.email.doctype.email_account.email_account.pull",
		],
		# Hourly but offset by 30 minutes
		"30 * * * *": [],
		# Daily but offset by 45 minutes
		"45 0 * * *": [],
	},
	"all": [
		"frappe.email.queue.flush",
		"frappe.email.queue.retry_sending_emails",
		"frappe.monitor.flush",
		"frappe.integrations.doctype.google_calendar.google_calendar.sync",
	],
	"hourly": [],
	# Maintenance queue happen roughly once an hour but don't align with wall-clock time of *:00
	# Use these for when you don't care about when the job runs but just need some guarantee for
	# frequency.
	"hourly_maintenance": [
		"frappe.model.utils.user_settings.sync_user_settings",
		"frappe.desk.page.backups.backups.delete_downloadable_backups",
		"frappe.desk.form.document_follow.send_hourly_updates",
		"frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request.process_data_deletion_request",
		"frappe.core.doctype.prepared_report.prepared_report.expire_stalled_report",
		"frappe.twofactor.delete_all_barcodes_for_users",
		"frappe.oauth.delete_oauth2_data",
		"frappe.website.doctype.web_page.web_page.check_publish_status",
	],
	"daily": [
		"frappe.desk.doctype.event.event.send_event_digest",
		"frappe.email.doctype.notification.notification.trigger_daily_alerts",
		"frappe.desk.form.document_follow.send_daily_updates",
	],
	"daily_long": [],
	"daily_maintenance": [
		"frappe.email.doctype.auto_email_report.auto_email_report.send_daily",
		"frappe.desk.notifications.clear_notifications",
		"frappe.sessions.clear_expired_sessions",
		"frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request.remove_unverified_record",
		"frappe.automation.doctype.auto_repeat.auto_repeat.make_auto_repeat_entry",
		"frappe.core.doctype.log_settings.log_settings.run_log_clean_up",
		"frappe.core.doctype.user_invitation.user_invitation.mark_expired_invitations",
	],
	"weekly_long": [
		"frappe.desk.form.document_follow.send_weekly_updates",
		"frappe.utils.change_log.check_for_update",
		"frappe.desk.doctype.changelog_feed.changelog_feed.fetch_changelog_feed",
	],
	"monthly": [
		"frappe.email.doctype.auto_email_report.auto_email_report.send_monthly",
	],
}

sounds = [
	{"name": "email", "src": "/assets/frappe/sounds/email.mp3", "volume": 0.1},
	{"name": "submit", "src": "/assets/frappe/sounds/submit.mp3", "volume": 0.1},
	{"name": "cancel", "src": "/assets/frappe/sounds/cancel.mp3", "volume": 0.1},
	{"name": "delete", "src": "/assets/frappe/sounds/delete.mp3", "volume": 0.05},
	{"name": "click", "src": "/assets/frappe/sounds/click.mp3", "volume": 0.05},
	{"name": "error", "src": "/assets/frappe/sounds/error.mp3", "volume": 0.1},
	{"name": "alert", "src": "/assets/frappe/sounds/alert.mp3", "volume": 0.2},
	# {"name": "chime", "src": "/assets/frappe/sounds/chime.mp3"},
]

setup_wizard_exception = [
	"frappe.desk.page.setup_wizard.setup_wizard.email_setup_wizard_exception",
	"frappe.desk.page.setup_wizard.setup_wizard.log_setup_wizard_exception",
]

before_migrate = ["frappe.core.doctype.patch_log.patch_log.before_migrate"]
after_migrate = [
	"frappe.website.doctype.website_theme.website_theme.after_migrate",
	"frappe.search.sqlite_search.build_index_in_background",
]

otp_methods = ["OTP App", "Email", "SMS"]

user_data_fields = [
	{"doctype": "Access Log", "strict": True},
	{"doctype": "Activity Log", "strict": True},
	{"doctype": "Comment", "strict": True},
	{
		"doctype": "Contact",
		"filter_by": "email_id",
		"redact_fields": ["first_name", "last_name", "phone", "mobile_no"],
		"rename": True,
	},
	{"doctype": "Contact Email", "filter_by": "email_id"},
	{
		"doctype": "Address",
		"filter_by": "email_id",
		"redact_fields": [
			"address_title",
			"address_line1",
			"address_line2",
			"city",
			"county",
			"state",
			"pincode",
			"phone",
			"fax",
		],
	},
	{
		"doctype": "Communication",
		"filter_by": "sender",
		"redact_fields": ["sender_full_name", "phone_no", "content"],
	},
	{"doctype": "Communication", "filter_by": "recipients"},
	{"doctype": "Email Group Member", "filter_by": "email"},
	{"doctype": "Email Unsubscribe", "filter_by": "email", "partial": True},
	{"doctype": "Email Queue", "filter_by": "sender"},
	{"doctype": "Email Queue Recipient", "filter_by": "recipient"},
	{
		"doctype": "File",
		"filter_by": "attached_to_name",
		"redact_fields": ["file_name", "file_url"],
	},
	{
		"doctype": "User",
		"filter_by": "name",
		"redact_fields": [
			"email",
			"username",
			"first_name",
			"middle_name",
			"last_name",
			"full_name",
			"birth_date",
			"user_image",
			"phone",
			"mobile_no",
			"location",
			"banner_image",
			"interest",
			"bio",
			"email_signature",
		],
	},
	{"doctype": "Version", "strict": True},
]

global_search_doctypes = {
	"Default": [
		{"doctype": "Contact"},
		{"doctype": "Address"},
		{"doctype": "ToDo"},
		{"doctype": "Note"},
		{"doctype": "Event"},
		{"doctype": "Dashboard"},
		{"doctype": "Country"},
		{"doctype": "Currency"},
		{"doctype": "Letter Head"},
		{"doctype": "Workflow"},
		{"doctype": "Web Page"},
		{"doctype": "Web Form"},
	]
}

override_whitelisted_methods = {
	# Legacy File APIs
	"frappe.utils.file_manager.download_file": "download_file",
	"frappe.core.doctype.file.file.download_file": "download_file",
	"frappe.core.doctype.file.file.unzip_file": "frappe.core.api.file.unzip_file",
	"frappe.core.doctype.file.file.get_attached_images": "frappe.core.api.file.get_attached_images",
	"frappe.core.doctype.file.file.get_files_in_folder": "frappe.core.api.file.get_files_in_folder",
	"frappe.core.doctype.file.file.get_files_by_search_text": "frappe.core.api.file.get_files_by_search_text",
	"frappe.core.doctype.file.file.get_max_file_size": "frappe.core.api.file.get_max_file_size",
	"frappe.core.doctype.file.file.create_new_folder": "frappe.core.api.file.create_new_folder",
	"frappe.core.doctype.file.file.move_file": "frappe.core.api.file.move_file",
	"frappe.core.doctype.file.file.zip_files": "frappe.core.api.file.zip_files",
	# Legacy (& Consistency) OAuth2 APIs
	"frappe.www.login.login_via_google": "frappe.integrations.oauth2_logins.login_via_google",
	"frappe.www.login.login_via_github": "frappe.integrations.oauth2_logins.login_via_github",
	"frappe.www.login.login_via_facebook": "frappe.integrations.oauth2_logins.login_via_facebook",
	"frappe.www.login.login_via_frappe": "frappe.integrations.oauth2_logins.login_via_frappe",
	"frappe.www.login.login_via_office365": "frappe.integrations.oauth2_logins.login_via_office365",
	"frappe.www.login.login_via_salesforce": "frappe.integrations.oauth2_logins.login_via_salesforce",
	"frappe.www.login.login_via_fairlogin": "frappe.integrations.oauth2_logins.login_via_fairlogin",
}

ignore_links_on_delete = [
	"Communication",
	"ToDo",
	"DocShare",
	"Email Unsubscribe",
	"Activity Log",
	"File",
	"Version",
	"Document Follow",
	"Comment",
	"View Log",
	"Tag Link",
	"Notification Log",
	"Email Queue",
	"Document Share Key",
	"Integration Request",
	"Unhandled Email",
	"Webhook Request Log",
	"Workspace",
	"Route History",
	"Access Log",
	"Permission Log",
]

# Request Hooks
before_request = [
	"frappe.recorder.record",
	"frappe.monitor.start",
	"frappe.rate_limiter.apply",
	"frappe.integrations.oauth2.set_cors_for_privileged_requests",
]

after_request = [
	"frappe.monitor.stop",
]

# Background Job Hooks
before_job = [
	"frappe.recorder.record",
	"frappe.monitor.start",
]

if os.getenv("FRAPPE_SENTRY_DSN") and (
	os.getenv("ENABLE_SENTRY_DB_MONITORING")
	or os.getenv("SENTRY_TRACING_SAMPLE_RATE")
	or os.getenv("SENTRY_PROFILING_SAMPLE_RATE")
):
	before_request.append("frappe.utils.sentry.set_sentry_context")
	before_job.append("frappe.utils.sentry.set_sentry_context")

after_job = [
	"frappe.recorder.dump",
	"frappe.monitor.stop",
	"frappe.utils.file_lock.release_document_locks",
]

extend_bootinfo = [
	"frappe.utils.telemetry.add_bootinfo",
	"frappe.core.doctype.user_permission.user_permission.send_user_permissions",
]

get_changelog_feed = "frappe.desk.doctype.changelog_feed.changelog_feed.get_feed"

export_python_type_annotations = True

standard_navbar_items = [
	{
		"item_label": "User Settings",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.route_to_user()",
		"is_standard": 1,
	},
	{
		"item_label": "Workspace Settings",
		"item_type": "Action",
		"action": "frappe.quick_edit('Workspace Settings')",
		"is_standard": 1,
	},
	{
		"item_label": "Session Defaults",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.setup_session_defaults()",
		"is_standard": 1,
	},
	{
		"item_label": "Reload",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.clear_cache()",
		"is_standard": 1,
	},
	{
		"item_label": "View Website",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.view_website()",
		"is_standard": 1,
	},
	{
		"item_label": "Apps",
		"item_type": "Route",
		"route": "/apps",
		"is_standard": 1,
	},
	{
		"item_label": "Toggle Full Width",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.toggle_full_width()",
		"is_standard": 1,
	},
	{
		"item_label": "Toggle Theme",
		"item_type": "Action",
		"action": "new frappe.ui.ThemeSwitcher().show()",
		"is_standard": 1,
	},
	{
		"item_type": "Separator",
		"is_standard": 1,
		"item_label": "",
	},
	{
		"item_label": "Log out",
		"item_type": "Action",
		"action": "frappe.app.logout()",
		"is_standard": 1,
	},
]

standard_help_items = [
	{
		"item_label": "About",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.show_about()",
		"is_standard": 1,
	},
	{
		"item_label": "Keyboard Shortcuts",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.show_shortcuts(event)",
		"is_standard": 1,
	},
	{
		"item_label": "System Health",
		"item_type": "Route",
		"route": "/app/system-health-report",
		"is_standard": 1,
	},
	{
		"item_label": "Frappe Support",
		"item_type": "Route",
		"route": "https://frappe.io/support",
		"is_standard": 1,
	},
]

# log doctype cleanups to automatically add in log settings
default_log_clearing_doctypes = {
	"Error Log": 14,
	"Email Queue": 30,
	"Scheduled Job Log": 7,
	"Submission Queue": 7,
	"Prepared Report": 14,
	"Webhook Request Log": 30,
	"Unhandled Email": 30,
	"Reminder": 30,
	"Integration Request": 90,
	"Activity Log": 90,
	"Route History": 90,
	"OAuth Bearer Token": 30,
	"API Request Log": 90,
}

# These keys will not be erased when doing frappe.clear_cache()
persistent_cache_keys = [
	"changelog-*",  # version update notifications
	"insert_queue_for_*",  # Deferred Insert
	"recorder-*",  # Recorder
	"global_search_queue",
	"monitor-transactions",
	"rate-limit-counter-*",
	"rl:*",
]

user_invitation = {
	"only_for": ["System Manager"],
}
