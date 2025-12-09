# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import getpass

import frappe
from frappe.geo.doctype.country.country import import_country_and_currency
from frappe.utils import cint
from frappe.utils.caching import site_cache
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
			"enable_telemtry": 1,
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


def auto_generate_icons_and_sidebar(app_name=None):
	"""Auto Create desktop icons and workspace sidebars."""
	from frappe.desk.doctype.desktop_icon.desktop_icon import create_desktop_icons
	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import (
		create_workspace_sidebar_for_workspaces,
	)

	try:
		print("Creating Desktop Icons")
		create_desktop_icons()
		print("Creating Workspace Sidebars")
		create_workspace_sidebar_for_workspaces()
		# Save the generated icons
		frappe.db.commit()  # nosemgrep
		# Save the genreated sidebar links
		frappe.db.commit()  # nosemgrep
	except Exception as e:
		print(f"Error creating icons {e}")


def delete_desktop_icon_and_sidebar(app_name, dry_run=False):
	frappe.get_hooks(app_name=app_name)
	app_title = frappe.get_hooks(app_name=app_name)["app_title"][0]
	icons_to_be_deleted = frappe.get_all(
		"Desktop Icon",
		pluck="name",
		or_filters=[
			["Desktop Icon", "name", "=", app_title],
			["Desktop Icon", "parent_icon", "=", app_title],
		],
	)
	print("Deleting Desktop Icons")
	for icon in icons_to_be_deleted:
		frappe.delete_doc_if_exists("Desktop Icon", icon)
	# Delete icons
	sidebar_to_be_deleted = frappe.get_all("Workspace Sidebar", pluck="name", filters={"app": app_name})
	print("Deleting Workspace Sidebars")
	for icon in sidebar_to_be_deleted:
		frappe.delete_doc_if_exists("Workspace Sidebar", icon)

	if dry_run:
		# Delete icons and sidebars
		frappe.db.commit()  # nosemgrep


@site_cache()
def auto_generate_sidebar_from_module():
	"""Auto generate sidebar from module"""
	sidebars = []
	for module in frappe.get_all("Module Def", pluck="name"):
		if not (
			frappe.db.exists("Workspace Sidebar", {"module": module})
			or frappe.db.exists("Workspace Sidebar", {"name": module})
		):
			module_info = get_module_info(module)
			sidebar_items = create_sidebar_items(module_info)
			sidebar = frappe.new_doc("Workspace Sidebar")
			sidebar.title = module
			sidebar.items = sidebar_items
			sidebar.module = module
			sidebar.header_icon = "hammer"
			sidebar.app = frappe.local.module_app.get(frappe.scrub(module), None)
			sidebars.append(sidebar)
	return sidebars


def get_module_info(module_name):
	entities = ["Workspace", "Dashboard", "DocType", "Report", "Page"]
	module_info = {}

	for entity in entities:
		module_info[entity] = {}
		filters = [{"module": module_name}]
		pluck = "name"
		fieldnames = ["name"]
		if entity.lower() == "doctype":
			filters.append({"istable": 0})
		if entity.lower() == "page":
			fieldnames.append("title")
			pluck = None
		module_info[entity] = frappe.get_all(
			entity, filters=filters, fields=fieldnames, pluck=pluck, order_by="creation asc"
		)

	# if module info has no workspaces, then move doctypes to the front
	if not module_info.get("Workspace"):
		module_info = {
			"DocType": module_info.get("DocType"),
			"Workspace": module_info.get("Workspace"),
			"Report": module_info.get("Report"),
			"Dashboard": module_info.get("Dashboard"),
			"Page": module_info.get("Page"),
		}
	top_doctypes = choose_top_doctypes(module_info.get("DocType"))
	if top_doctypes:
		module_info["DocType"] = choose_top_doctypes(module_info.get("DocType"))
	return module_info


def choose_top_doctypes(doctype_names):
	doctype_limit = 3
	if len(doctype_names) > doctype_limit:
		try:
			doctype_count_map = {}
			for doctype in doctype_names:
				doctype_count_map[doctype] = frappe.db.count(doctype)
			top_doctypes = [
				name
				for name, count in sorted(doctype_count_map.items(), key=lambda x: x[1], reverse=True)[
					:doctype_limit
				]
			]
			return top_doctypes
		except frappe.db.ProgrammingError:
			# catches table not found errors
			return None


def create_sidebar_items(module_info):
	sidebar_items = []
	idx = 1

	section_entities = {"report": "Reports", "dashboard": "Dashboards", "page": "Pages"}

	for entity, items in module_info.items():
		section_break_added = False
		entity_lower = entity.lower()

		if entity_lower in section_entities:
			if entity_lower == "report":
				section_break = add_section_breaks("Reports", idx)
			elif entity_lower in ("dashboard", "page") and len(items) > 1:
				section_break = add_section_breaks(section_entities[entity_lower], idx)
				section_break_added = True
			sidebar_items.append(section_break)
			idx += 1

		for item in items:
			print(entity, item)
			item_info = {"label": item, "type": "Link", "link_type": entity, "link_to": item, "idx": idx}

			if entity_lower == "report":
				item_info["child"] = 1
				item_info["icon"] = "table"

			if entity_lower == "page":
				item_info["label"] = item.get("title")
				item_info["link_to"] = item.get("name")

			if entity_lower == "workspace":
				item_info["icon"] = "home"
				item_info["icon"] = "wallpaper"

			if entity_lower == "page":
				item_info["icon"] = "panel-top"

			if entity_lower == "doctype" and "settings" in item.lower():
				item_info["icon"] = "settings"

			if section_break_added:
				item_info["child"] = 1

			sidebar_item = frappe.new_doc("Workspace Sidebar Item")
			sidebar_item.update(item_info)
			sidebar_items.append(sidebar_item)

			idx += 1

	return sidebar_items


def add_section_breaks(label, idx):
	section_break = frappe.new_doc("Workspace Sidebar Item")
	section_break.update({"label": label, "type": "Section Break", "idx": idx})
	return section_break
