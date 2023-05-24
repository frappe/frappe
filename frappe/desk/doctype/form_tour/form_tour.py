# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files


class FormTour(Document):
	def before_save(self):
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
		if self.ui_tour:
			form_tour_settings = frappe.get_doc("Form Tour Settings", "Form Tour Settings")
			in_settings = False
			child_index = 0
			for tour in form_tour_settings.form_tours:
				if tour.form_tour == self.name:
					in_settings = True
					child_index = tour.idx
					form_tour_settings.remove(tour)
			if not in_settings:
				child_index = len(form_tour_settings.form_tours) + 1
			child = frappe.new_doc("Form Tour Settings Item")
			child.update(
				{
					"idx": child_index,
					"form_tour": self.name,
					"parent": "Form Tour Settings",
					"parentfield": "form_tours",
					"parenttype": "Form Tour Settings",
				}
			)
			child.save()
			form_tour_settings.form_tours.insert(child_index, child)
			form_tour_settings.save()
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files([["Form Tour", self.name]], self.module)

	def on_trash(self):
		if self.ui_tour:
			form_tour_settings = frappe.get_doc("Form Tour Settings", "Form Tour Settings")
			for tour in form_tour_settings.form_tours:
				if tour.form_tour == self.name:
					form_tour_settings.remove(tour)
			form_tour_settings.save()


@frappe.whitelist()
def reset_tour(tour_name):
	for user in frappe.get_all("User"):
		user_doc = frappe.get_doc("User", user.name)
		onboarding_status = frappe.parse_json(user_doc.onboarding_status)
		onboarding_status.pop(tour_name, None)
		user_doc.onboarding_status = frappe.as_json(onboarding_status)
		user_doc.save()
