# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.core.page.permission_manager.permission_manager import get_permissions
from frappe.model.document import Document


class RoleReplication(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		existing_role: DF.Link | None
		new_role: DF.Data | None
	# end: auto-generated types

	@frappe.whitelist()
	def replicate_role(self):
		frappe.only_for("System Manager")

		new_role = frappe.db.get_value("Role", self.new_role, "name")
		if not new_role:
			new_role = frappe.get_doc({"doctype": "Role", "role_name": self.new_role}).insert().name

		perms = get_permissions(role=self.existing_role)

		# Get doctypes that already have Custom DocPerm for the existing role
		existing_custom_docperms = set(
			frappe.get_all(
				"Custom DocPerm", filters={"role": self.existing_role}, pluck="parent", distinct=True
			)
		)

		for perm in perms:
			# If the original role's permission comes from DocPerm (not Custom DocPerm),
			# we need to also create a Custom DocPerm for the original role.
			# Otherwise, once we create Custom DocPerm for the new role, the original
			# role's DocPerm will be hidden by get_all_perms() logic.
			if perm.get("parent") and perm["parent"] not in existing_custom_docperms:
				frappe.get_doc(
					{
						"doctype": "Custom DocPerm",
						**perm,
						"name": None,
						"creation": None,
						"modified": None,
						"modified_by": None,
						"owner": None,
						"linked_doctypes": None,
					}
				).insert()
				existing_custom_docperms.add(perm["parent"])

			# Create Custom DocPerm for the new role
			frappe.get_doc(
				{
					"doctype": "Custom DocPerm",
					**perm,
					"name": None,
					"creation": None,
					"modified": None,
					"modified_by": None,
					"owner": None,
					"linked_doctypes": None,
					"role": new_role,
				}
			).insert()
