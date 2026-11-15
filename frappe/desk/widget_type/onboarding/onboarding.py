import frappe
from frappe import _
from frappe.desk.widgets import WidgetType


class Onboarding(WidgetType):
	"""A Module Onboarding's steps, until it is complete."""

	# progress made on another page shows within a minute
	cache_ttl = 60

	def has_permission(self, user=None) -> bool:
		return True

	def get_data(self, filters=None):
		from frappe.desk.doctype.onboarding_step.onboarding_step import get_step_details

		doc = open_onboarding(self.config.get("onboarding"))
		if not doc:
			return None
		steps = [get_step_details(row.step, row.is_optional) for row in doc.steps]
		return {"title": _(doc.title), "steps": steps}


def open_onboarding(name: str):
	"""The Module Onboarding `name` while the session user still has it to do, else None."""
	if not name or not frappe.get_system_settings("enable_onboarding"):
		return None

	# a block can outlive the onboarding it names; that hides the block, not the workspace
	is_complete = frappe.db.get_value("Module Onboarding", name, "is_complete")
	if is_complete is None or is_complete:
		return None

	doc = frappe.get_doc("Module Onboarding", name)
	if not set(doc.get_allowed_roles()) & set(frappe.get_roles()):
		return None
	return None if doc.check_completion() else doc
