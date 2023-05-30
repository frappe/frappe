# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files


class FormTour(Document):
	def before_save(self):
		if self.is_standard and not self.module:
			if self.workspace_name:
				self.module = frappe.db.get_value("Workspace", self.workspace_name, "module")
			elif self.dashboard_name:
				dashboard_doctype = frappe.db.get_value("Dashboard", self.dashboard_name, "module")
				self.module = frappe.db.get_value("DocType", dashboard_doctype, "module")
			else:
				self.module = "Desk"
		if not self.ui_tour:
			meta = frappe.get_meta(self.reference_doctype)
			for step in self.steps:
				if step.is_table_field and step.parent_fieldname:
					parent_field_df = meta.get_field(step.parent_fieldname)
					step.child_doctype = parent_field_df.options
					field_df = frappe.get_meta(step.child_doctype).get_field(step.fieldname)
					step.label = field_df.label
					step.fieldtype = field_df.fieldtype
				else:
					field_df = meta.get_field(step.fieldname)
					step.label = field_df.label
					step.fieldtype = field_df.fieldtype

	def on_update(self):
		frappe.cache().delete_key("bootinfo")

		if frappe.conf.developer_mode and self.is_standard:
			export_to_files([["Form Tour", self.name]], self.module)

	def on_trash(self):
		frappe.cache().delete_key("bootinfo")


@frappe.whitelist()
def reset_tour(tour_name):
	for user in frappe.get_all("User"):
		user_doc = frappe.get_doc("User", user.name)
		onboarding_status = frappe.parse_json(user_doc.onboarding_status)
		onboarding_status.pop(tour_name, None)
		user_doc.onboarding_status = frappe.as_json(onboarding_status)
		user_doc.save()


@frappe.whitelist()
def update_user_status(value, step):
	from frappe.utils.telemetry import capture

	step = frappe.parse_json(step)
	tour = frappe.parse_json(value)

	capture(
		frappe.scrub(f"{step.parent}_{step.title}"),
		app="frappe_ui_tours",
		properties={"is_completed": tour.is_completed},
	)
	frappe.db.set_value(
		"User", frappe.session.user, "onboarding_status", value, update_modified=False
	)

	frappe.cache().hdel("bootinfo", frappe.session.user)


def get_onboarding_ui_tours():
	if not frappe.get_system_settings("enable_onboarding"):
		return []

	ui_tours = frappe.get_all("Form Tour", filters={"ui_tour": 1}, fields=["page_route", "name"])

	return [[tour.name, json.loads(tour.page_route)] for tour in ui_tours]
