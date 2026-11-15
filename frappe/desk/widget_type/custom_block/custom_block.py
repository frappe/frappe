import frappe
from frappe.desk.widgets import WidgetType


class CustomBlock(WidgetType):
	"""A site's Custom HTML Block, for the roles it names; a private one only for its owner."""

	def has_permission(self, user=None) -> bool:
		name = self.config.get("custom_block")
		block = frappe.db.get_value("Custom HTML Block", name, ["private", "owner"], as_dict=True)
		if not block or (block.private and block.owner != frappe.session.user):
			return False
		roles = frappe.get_all(
			"Has Role", filters={"parent": name, "parenttype": "Custom HTML Block"}, pluck="role"
		)
		return (not roles or bool(set(roles) & set(frappe.get_roles()))) and super().has_permission(user)

	def get_data(self, filters=None):
		fields = ["html", "style", "script"]
		return frappe.db.get_value("Custom HTML Block", self.config.get("custom_block"), fields, as_dict=True)
