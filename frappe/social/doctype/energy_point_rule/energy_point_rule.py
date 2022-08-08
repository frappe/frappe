# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
import frappe.cache_manager
from frappe import _
from frappe.core.doctype.user.user import get_enabled_users
from frappe.model import log_types
from frappe.model.document import Document
from frappe.social.doctype.energy_point_log.energy_point_log import create_energy_points_log
from frappe.social.doctype.energy_point_settings.energy_point_settings import (
	is_energy_point_enabled,
)


class EnergyPointRule(Document):
	def on_update(self):
		frappe.cache_manager.clear_doctype_map("Energy Point Rule", self.reference_doctype)

	def on_trash(self):
		frappe.cache_manager.clear_doctype_map("Energy Point Rule", self.reference_doctype)

	def apply(self, doc):
		if self.rule_condition_satisfied(doc):
			multiplier = 1

			points = self.points
			if self.multiplier_field:
				multiplier = doc.get(self.multiplier_field) or 1
				points = round(points * multiplier)
				max_points = self.max_points
				if max_points and points > max_points:
					points = max_points

			reference_doctype = doc.doctype
			reference_name = doc.name
			users = []
			if self.for_assigned_users:
				users = doc.get_assigned_users()
			else:
				users = [doc.get(self.user_field)]
			rule = self.name

			# incase of zero as result after roundoff
			if not points:
				return

			try:
				for user in users:
					if not is_eligible_user(user):
						continue
					create_energy_points_log(
						reference_doctype,
						reference_name,
						{"points": points, "user": user, "rule": rule},
						self.apply_only_once,
					)
			except Exception as e:
				self.log_error("Energy points failed")

	def rule_condition_satisfied(self, doc):
		if self.for_doc_event == "New":
			# indicates that this was a new doc
			return doc.get_doc_before_save() is None
		if self.for_doc_event == "Submit":
			return doc.docstatus.is_submitted()
		if self.for_doc_event == "Cancel":
			return doc.docstatus.is_cancelled()
		if self.for_doc_event == "Value Change":
			field_to_check = self.field_to_check
			if not field_to_check:
				return False
			doc_before_save = doc.get_doc_before_save()
			# check if the field has been changed
			# if condition is set check if it is satisfied
			return (
				doc_before_save
				and doc_before_save.get(field_to_check) != doc.get(field_to_check)
				and (not self.condition or self.eval_condition(doc))
			)

		if self.for_doc_event == "Custom" and self.condition:
			return self.eval_condition(doc)
		return False

	def eval_condition(self, doc):
		return self.condition and frappe.safe_eval(self.condition, None, {"doc": doc.as_dict()})


def process_energy_points(doc, state):
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
		or doc.doctype in log_types
	):
		return

	if not is_energy_point_enabled():
		return

	old_doc = doc.get_doc_before_save()

	# check if doc has been cancelled
	if old_doc and old_doc.docstatus.is_submitted() and doc.docstatus.is_cancelled():
		return revert_points_for_cancelled_doc(doc)

	for d in frappe.cache_manager.get_doctype_map(
		"Energy Point Rule", doc.doctype, dict(reference_doctype=doc.doctype, enabled=1)
	):
		frappe.get_doc("Energy Point Rule", d.get("name")).apply(doc)


def revert_points_for_cancelled_doc(doc):
	energy_point_logs = frappe.get_all(
		"Energy Point Log",
		{"reference_doctype": doc.doctype, "reference_name": doc.name, "type": "Auto"},
	)
	for log in energy_point_logs:
		reference_log = frappe.get_doc("Energy Point Log", log.name)
		reference_log.revert(_("Reference document has been cancelled"), ignore_permissions=True)


def get_energy_point_doctypes():
	return [
		d.reference_doctype
		for d in frappe.get_all("Energy Point Rule", ["reference_doctype"], {"enabled": 1})
	]


def is_eligible_user(user):
	"""Checks if user is eligible to get energy points"""
	enabled_users = get_enabled_users()
	return user and user in enabled_users and user != "Administrator"
