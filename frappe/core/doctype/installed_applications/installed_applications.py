# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import Document


class InvalidAppOrder(frappe.ValidationError):
	pass


class InstalledApplications(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.installed_application.installed_application import InstalledApplication
		from frappe.types import DF

		installed_applications: DF.Table[InstalledApplication]
	# end: auto-generated types

	def update_versions(self):
		app_wise_setup_details = self.get_app_wise_setup_details()

		self.delete_key("installed_applications")
		for app in frappe.utils.get_installed_apps_info():
			has_setup_wizard = 0
			if app.get("app_name") == "frappe" or frappe.get_hooks(app_name=app.get("app_name")).get(
				"setup_wizard_stages"
			):
				has_setup_wizard = 1

			self.append(
				"installed_applications",
				{
					"app_name": app.get("app_name"),
					"app_version": app.get("version") or "UNVERSIONED",
					"git_branch": app.get("branch") or "UNVERSIONED",
					"has_setup_wizard": has_setup_wizard,
					"is_setup_complete": app_wise_setup_details.get(app.get("app_name")) or 0,
				},
			)

		self.save()

	def get_app_wise_setup_details(self):
		"""Get app wise setup details from the Installed Application doctype"""
		return frappe._dict(
			frappe.get_all(
				"Installed Application",
				fields=["app_name", "is_setup_complete"],
				filters={"has_setup_wizard": 1},
				as_list=True,
			)
		)


@frappe.whitelist()
def update_installed_apps_order(new_order: list[str] | str):
	"""Change the ordering of `installed_apps` global

	This list is used to resolve hooks and by default it's order of installation on site.

	Sometimes it might not be the ordering you want, so thie function is provided to override it.
	"""
	frappe.only_for("System Manager")

	if isinstance(new_order, str):
		new_order = json.loads(new_order)

	frappe.local.request_cache and frappe.local.request_cache.clear()
	existing_order = frappe.get_installed_apps(_ensure_on_bench=True)

	if set(existing_order) != set(new_order) or not isinstance(new_order, list):
		frappe.throw(
			_("You are only allowed to update order, do not remove or add apps."), exc=InvalidAppOrder
		)

	# Ensure frappe is always first regardless of user's preference.
	if "frappe" in new_order:
		new_order.remove("frappe")
	new_order.insert(0, "frappe")

	frappe.db.set_global("installed_apps", json.dumps(new_order))

	_create_version_log_for_change(existing_order, new_order)


def _create_version_log_for_change(old, new):
	version = frappe.new_doc("Version")
	version.ref_doctype = "DefaultValue"
	version.docname = "installed_apps"
	version.data = frappe.as_json({"changed": [["current", json.dumps(old), json.dumps(new)]]})
	version.flags.ignore_links = True  # This is a fake doctype
	version.flags.ignore_permissions = True
	version.insert()


@frappe.whitelist()
def get_installed_app_order() -> list[str]:
	frappe.only_for("System Manager")

	return frappe.get_installed_apps(_ensure_on_bench=True)


@frappe.request_cache
def get_setup_wizard_completed_apps():
	"""Get list of apps that have completed setup wizard"""
	return frappe.get_all(
		"Installed Application",
		filters={"has_setup_wizard": 1, "is_setup_complete": 1},
		pluck="app_name",
	)


@frappe.request_cache
def get_setup_wizard_not_required_apps():
	"""Get list of apps that do not require setup wizard"""
	return frappe.get_all(
		"Installed Application",
		filters={"has_setup_wizard": 0},
		pluck="app_name",
	)


@frappe.request_cache
def get_apps_with_incomplete_dependencies(current_app):
	"""Get apps with incomplete dependencies."""
	dependent_apps = ["frappe"]

	if apps := frappe.get_hooks("required_apps", app_name=current_app):
		dependent_apps.extend(apps)

	parsed_apps = []
	for apps in dependent_apps:
		apps = apps.split("/")
		parsed_apps.extend(apps)

	pending_apps = get_setup_wizard_pending_apps(parsed_apps)

	return pending_apps


@frappe.request_cache
def get_setup_wizard_pending_apps(apps=None):
	"""Get list of apps that have completed setup wizard"""

	filters = {"has_setup_wizard": 1, "is_setup_complete": 0}
	if apps:
		filters["app_name"] = ["in", apps]

	return frappe.get_all(
		"Installed Application",
		filters=filters,
		order_by="idx",
		pluck="app_name",
	)
