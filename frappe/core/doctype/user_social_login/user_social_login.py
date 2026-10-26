# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class UserSocialLogin(Document):
	_DOCTYPE_NAME = "User Social Login"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		provider: DF.Data | None
		userid: DF.Data | None
		username: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.disallow_frappe_userid_change()

	def disallow_frappe_userid_change(self):
		"""`userid` for the `frappe` provider is this site's OIDC `sub`; it is managed on the
		parent User, so a direct write to this row cannot set or change it."""
		if self.provider != "frappe":
			return

		stored_userid = None
		if not self.is_new():
			stored_userid = frappe.db.get_value(self.doctype, self.name, "userid")

		if self.userid != stored_userid:
			frappe.throw(_("Cannot change the sign-in identifier for the frappe provider."))
