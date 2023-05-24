from . import __version__ as app_version

app_name = "frappe"
app_title = "Frappe Framework"
app_publisher = "Frappe Technologies"
app_description = "Full stack web framework with Python, Javascript, MariaDB, Redis, Node"
source_link = "https://github.com/frappe/frappe"
app_license = "MIT"
app_logo_url = "/assets/frappe/images/frappe-framework-logo.svg"

develop_version = "14.x.x-develop"

app_email = "developers@frappe.io"

docs_app = "frappe_docs"

translator_url = "https://translate.erpnext.com"

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
]
app_include_css = [
	"desk.bundle.css",
	"report.bundle.css",
]

doctype_js = {
	"Web Page": "public/js/frappe/utils/web_template.js",
	"Website Settings": "public/js/frappe/utils/web_template.js",
}

web_include_js = ["website_script.js"]

web_include_css = []

email_css = ["email.bundle.css"]

website_route_rules = [
	{"from_route": "/blog/<category>", "to_route": "Blog Post"},
	{"from_route": "/kb/<category>", "to_route": "Help Article"},
	{"from_route": "/newsletters", "to_route": "Newsletter"},
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

leaderboards = "frappe.desk.leaderboard.get_leaderboards"

# login

on_session_creation = [
	"frappe.core.doctype.activity_log.feed.login_feed",
	"frappe.core.doctype.user.user.notify_admin_access_to_system_manager",
]

on_logout = (
	"frappe.core.doctype.session_default_settings.session_default_settings.clear_session_defaults"
)

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
}

has_permission = {
	"Event": "frappe.desk.doctype.event.event.has_permission",
	"ToDo": "frappe.desk.doctype.todo.todo.has_permission",
	"User": "frappe.core.doctype.user.user.has_permission",
	"Note": "frappe.desk.doctype.note.note.has_permission",
	"Dashboard Chart": "frappe.desk.doctype.dashboard_chart.dashboard_chart.has_permission",
	"Number Card": "frappe.desk.doctype.number_card.number_card.has_permission",
	"Kanban Board": "frappe.desk.doctype.kanban_board.kanban_board.has_permission",
	"Contact": "frappe.contacts.address_and_contact.has_permission",
	"Address": "frappe.contacts.address_and_contact.has_permission",
	"Communication": "frappe.core.doctype.communication.communication.has_permission",
	"Workflow Action": "frappe.workflow.doctype.workflow_action.workflow_action.has_permission",
	"File": "frappe.core.doctype.file.file.has_permission",
	"Prepared Report": "frappe.core.doctype.prepared_report.prepared_report.has_permission",
}

has_website_permission = {
	"Address": "frappe.contacts.doctype.address.address.has_website_permission"
}

jinja = {
	"methods": "frappe.utils.jinja_globals",
	"filters": [
		"frappe.utils.data.global_date_format",
		"frappe.utils.markdown",
		"frappe.website.utils.get_shade",
		"frappe.website.utils.abs_url",
	],
}

standard_queries = {"User": "frappe.core.doctype.user.user.user_query"}

doc_events = {
	"*": {
		"after_insert": [
			"frappe.event_streaming.doctype.event_update_log.event_update_log.notify_consumers"
		],
		"on_update": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.core.doctype.activity_log.feed.update_feed",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.automation.doctype.assignment_rule.assignment_rule.apply",
			"frappe.core.doctype.file.utils.attach_files_to_document",
			"frappe.event_streaming.doctype.event_update_log.event_update_log.notify_consumers",
			"frappe.automation.doctype.assignment_rule.assignment_rule.update_due_date",
			"frappe.core.doctype.user_type.user_type.apply_permissions_for_non_standard_user_type",
		],
		"after_rename": "frappe.desk.notifications.clear_doctype_notifications",
		"on_cancel": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.event_streaming.doctype.event_update_log.event_update_log.notify_consumers",
		],
		"on_trash": [
			"frappe.desk.notifications.clear_doctype_notifications",
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"frappe.event_streaming.doctype.event_update_log.event_update_log.notify_consumers",
		],
		"on_update_after_submit": [
			"frappe.workflow.doctype.workflow_action.workflow_action.process_workflow_actions"
		],
		"on_change": [
			"frappe.social.doctype.energy_point_rule.energy_point_rule.process_energy_points",
			"frappe.automation.doctype.milestone_tracker.milestone_tracker.evaluate_milestone",
		],
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
		"on_update": "frappe.cache_manager.build_domain_restriced_doctype_cache",
	},
	"Page": {
		"on_update": "frappe.cache_manager.build_domain_restriced_page_cache",
	},
}

scheduler_events = {
	"cron": {
		"0/15 * * * *": [
			"frappe.oauth.delete_oauth2_data",
			"frappe.website.doctype.web_page.web_page.check_publish_status",
			"frappe.twofactor.delete_all_barcodes_for_users",
		],
		"0/10 * * * *": [
			"frappe.email.doctype.email_account.email_account.pull",
		],
		# Hourly but offset by 30 minutes
		# "30 * * * *": [
		#
		# ],
		# Daily but offset by 45 minutes
		"45 0 * * *": [
			"frappe.core.doctype.log_settings.log_settings.run_log_clean_up",
		],
	},
	"all": [
		"frappe.email.queue.flush",
		"frappe.email.doctype.email_account.email_account.pull",
		"frappe.email.doctype.email_account.email_account.notify_unreplied",
		"frappe.utils.global_search.sync_global_search",
		"frappe.monitor.flush",
	],
	"hourly": [
		"frappe.model.utils.link_count.update_link_count",
		"frappe.model.utils.user_settings.sync_user_settings",
		"frappe.utils.error.collect_error_snapshots",
		"frappe.desk.page.backups.backups.delete_downloadable_backups",
		"frappe.deferred_insert.save_to_db",
		"frappe.desk.form.document_follow.send_hourly_updates",
		"frappe.integrations.doctype.google_calendar.google_calendar.sync",
		"frappe.email.doctype.newsletter.newsletter.send_scheduled_email",
		"frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request.process_data_deletion_request",
	],
	"daily": [
		"frappe.email.queue.set_expiry_for_email_queue",
		"frappe.desk.notifications.clear_notifications",
		"frappe.desk.doctype.event.event.send_event_digest",
		"frappe.sessions.clear_expired_sessions",
		"frappe.email.doctype.notification.notification.trigger_daily_alerts",
		"frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request.remove_unverified_record",
		"frappe.desk.form.document_follow.send_daily_updates",
		"frappe.social.doctype.energy_point_settings.energy_point_settings.allocate_review_points",
		"frappe.integrations.doctype.google_contacts.google_contacts.sync",
		"frappe.automation.doctype.auto_repeat.auto_repeat.make_auto_repeat_entry",
		"frappe.automation.doctype.auto_repeat.auto_repeat.set_auto_repeat_as_completed",
		"frappe.email.doctype.unhandled_email.unhandled_email.remove_old_unhandled_emails",
	],
	"daily_long": [
		"frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backups_daily",
		"frappe.utils.change_log.check_for_update",
		"frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_daily",
		"frappe.email.doctype.auto_email_report.auto_email_report.send_daily",
		"frappe.integrations.doctype.google_drive.google_drive.daily_backup",
	],
	"weekly_long": [
		"frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backups_weekly",
		"frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_weekly",
		"frappe.desk.form.document_follow.send_weekly_updates",
		"frappe.social.doctype.energy_point_log.energy_point_log.send_weekly_summary",
		"frappe.integrations.doctype.google_drive.google_drive.weekly_backup",
	],
	"monthly": [
		"frappe.email.doctype.auto_email_report.auto_email_report.send_monthly",
		"frappe.social.doctype.energy_point_log.energy_point_log.send_monthly_summary",
	],
	"monthly_long": [
		"frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_monthly"
	],
}

get_translated_dict = {
	("doctype", "System Settings"): "frappe.geo.country_info.get_translated_dict",
	("page", "setup-wizard"): "frappe.geo.country_info.get_translated_dict",
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

before_migrate = []
after_migrate = ["frappe.website.doctype.website_theme.website_theme.after_migrate"]

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
		{"doctype": "Blog Post"},
		{"doctype": "Dashboard"},
		{"doctype": "Country"},
		{"doctype": "Currency"},
		{"doctype": "Newsletter"},
		{"doctype": "Letter Head"},
		{"doctype": "Workflow"},
		{"doctype": "Web Page"},
		{"doctype": "Web Form"},
	]
}

override_whitelisted_methods = {
	# Legacy File APIs
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
]

# Request Hooks
before_request = [
	"frappe.recorder.record",
	"frappe.monitor.start",
	"frappe.rate_limiter.apply",
]
after_request = ["frappe.rate_limiter.update", "frappe.monitor.stop", "frappe.recorder.dump"]

# Background Job Hooks
before_job = [
	"frappe.monitor.start",
]
after_job = [
	"frappe.monitor.stop",
	"frappe.utils.file_lock.release_document_locks",
]

extend_bootinfo = [
	"frappe.utils.telemetry.add_bootinfo",
]
