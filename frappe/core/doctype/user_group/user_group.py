# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe

# import frappe
from frappe.model.document import Document


class UserGroup(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.user_group_member.user_group_member import UserGroupMember
		from frappe.types import DF

		user_group_members: DF.TableMultiSelect[UserGroupMember]
	# end: auto-generated types

	def after_insert(self):
		frappe.cache.delete_key("user_groups")

	def on_trash(self):
		frappe.cache.delete_key("user_groups")


@frappe.whitelist()
def get_users_from_group(user_group):
	"""This function fetches users from a given user group"""
	# Did not want to directly make a db call from the client-side code to fetch users from the group
	# Checked other code onlt assign_to.js is adding users which is making a db call
	try:
		if not frappe.has_permission("User Group", "read", user_group):
			message = frappe._("You do not have permission to read this User Group")
			frappe.throw(message)
		return frappe.get_list(
			"User Group Member", parent_doctype="User Group", filters={"parent": user_group}, fields=["user"]
		)
	except Exception as e:
		frappe.log_error(title="Error fetching users from user group", message=str(e))
		return []
