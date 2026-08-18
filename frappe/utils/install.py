# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import getpass

import frappe
from frappe.desk.doctype.notification_type.notification_type import install_notification_types
from frappe.email.doctype.notification.notification import install_notification_templates
from frappe.geo.doctype.country.country import import_country_and_currency
from frappe.utils import cint
from frappe.utils.password import update_password


def before_install():
	frappe.reload_doc("core", "doctype", "doctype_state")
	frappe.reload_doc("core", "doctype", "docfield")
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "doctype_action")
	frappe.reload_doc("core", "doctype", "doctype_link")
	frappe.reload_doc("desk", "doctype", "form_tour_step")
	frappe.reload_doc("desk", "doctype", "form_tour")
	frappe.reload_doc("core", "doctype", "doctype")
	frappe.clear_cache()


def after_install():
	create_user_type()
	install_basic_docs()

	from frappe.core.doctype.file.utils import make_home_folder
	from frappe.core.doctype.language.language import sync_languages

	make_home_folder()
	import_country_and_currency()
	sync_languages()

	# save default print setting
	print_settings = frappe.get_doc("Print Settings")
	print_settings.save()

	# all roles to admin
	frappe.get_doc("User", "Administrator").add_roles(*frappe.get_all("Role", pluck="name"))

	# update admin password
	update_password("Administrator", get_admin_password())

	if not frappe.conf.skip_setup_wizard:
		# only set home_page if the value doesn't exist in the db
		if not frappe.db.get_default("desktop:home_page"):
			frappe.db.set_default("desktop:home_page", "setup-wizard")

	# clear test log
	from frappe.tests.utils.generators import _clear_test_log

	_clear_test_log()

	add_standard_navbar_items()

	# standard notification types (must precede templates: the Notification
	# `notification_type` field defaults to "Alert", so templates link to it)
	install_notification_types()

	# default templates
	install_notification_templates()

	frappe.db.commit()


def create_user_type():
	for user_type in ["System User", "Website User"]:
		if not frappe.db.exists("User Type", user_type):
			frappe.get_doc({"doctype": "User Type", "name": user_type, "is_standard": 1}).insert(
				ignore_permissions=True
			)


def install_basic_docs():
	# core users / roles
	install_docs = [
		{
			"doctype": "User",
			"name": "Administrator",
			"first_name": "Administrator",
			"email": "admin@example.com",
			"enabled": 1,
			"is_admin": 1,
			"roles": [{"role": "Administrator"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{
			"doctype": "User",
			"name": "Guest",
			"first_name": "Guest",
			"email": "guest@example.com",
			"enabled": 1,
			"is_guest": 1,
			"roles": [{"role": "Guest"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Pending",
			"icon": "question-sign",
			"style": "",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Approved",
			"icon": "ok-sign",
			"style": "Success",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Rejected",
			"icon": "remove",
			"style": "Danger",
		},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Approve"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Reject"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Review"},
	]

	for d in install_docs:
		try:
			frappe.get_doc(d).insert(ignore_if_duplicate=True)
		except frappe.NameError:
			pass


def get_admin_password():
	return frappe.conf.get("admin_password") or getpass.getpass("Set Administrator password: ")


def before_tests():
	if len(frappe.get_installed_apps()) > 1:
		# don't run before tests if any other app is installed
		return

	frappe.db.truncate("Custom Field")
	frappe.db.truncate("Event")

	frappe.clear_cache()

	# complete setup if missing
	if not frappe.is_setup_complete():
		complete_setup_wizard()

	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
	frappe.db.commit()
	frappe.clear_cache()


def complete_setup_wizard():
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"email": "test@erpnext.com",
			"full_name": "Test User",
			"password": "test",
			"country": "United States",
			"timezone": "America/New_York",
			"currency": "USD",
			"enable_telemetry": 1,
		}
	)


def add_standard_navbar_items():
	navbar_settings = frappe.get_single("Navbar Settings")

	# don't add settings/help options if they're already present
	if navbar_settings.settings_dropdown and navbar_settings.help_dropdown:
		return

	navbar_settings.settings_dropdown = []
	navbar_settings.help_dropdown = []

	for item in frappe.get_hooks("standard_navbar_items"):
		navbar_settings.append("settings_dropdown", item)

	for item in frappe.get_hooks("standard_help_items"):
		navbar_settings.append("help_dropdown", item)

	navbar_settings.save()


def create_desktop_icons_for_app(app_name=None):
	"""Seed Desktop Icons after an app is installed.

	Only the Desktop Icon grid reads these rows, so there's nothing to do unless
	Desktop Settings -> Desktop Page is `Desktop Icons`. Regenerates all icons, which is
	idempotent -- it only creates the ones that don't already exist.
	"""
	from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page

	if not is_desktop_icons_page():
		return

	from frappe.desk.doctype.desktop_icon.desktop_icon import create_desktop_icons

	try:
		create_desktop_icons()
		frappe.db.commit()  # nosemgrep
	except Exception as e:
		print(f"Error creating desktop icons: {e}")


def delete_desktop_icons_for_app(app_name, dry_run=False):
	"""Remove an uninstalled app's Desktop Icons."""
	# `remove_app` fires after_app_uninstall hooks even on a dry run, so respect dry_run
	# ourselves: preview only, don't touch the database.
	if dry_run:
		return

	# Icons are named/labelled by the app's title (Desktop Icon autoname is `field:label`,
	# set to app_title in create_desktop_icons_from_installed_apps), not the package name --
	# so match on the `app_title` hook, else the filters never hit and rows are orphaned.
	# No hook means the seeding never created an icon for this app either, so there's
	# nothing to clean up; indexing an empty list here would raise on uninstall instead.
	app_title = (frappe.get_hooks("app_title", app_name=app_name) or [None])[0]
	if not app_title:
		return

	icons_to_delete = frappe.get_all(
		"Desktop Icon",
		pluck="name",
		or_filters=[
			["Desktop Icon", "name", "=", app_title],
			["Desktop Icon", "parent_icon", "=", app_title],
		],
	)
	for icon in icons_to_delete:
		frappe.delete_doc_if_exists("Desktop Icon", icon)

	# after_app_uninstall runs after remove_app's own commit, so persist the deletions here.
	frappe.db.commit()  # nosemgrep
