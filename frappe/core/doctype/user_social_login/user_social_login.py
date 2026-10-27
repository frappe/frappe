# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class UserSocialLogin(Document):
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
		parent User, so a direct write to this row cannot set or change it, nor relabel another
		provider's row as `frappe` to smuggle one in."""
		before = (
			None
			if self.is_new()
			else frappe.db.get_value(self.doctype, self.name, ["provider", "userid"], as_dict=True)
		)
		stored_provider = before.provider if before else None

		if self.provider != "frappe" and stored_provider != "frappe":
			return

		if stored_provider and stored_provider != self.provider:
			frappe.throw(_("Cannot change the provider of this sign-in identifier."))

		stored_userid = before.userid if stored_provider == "frappe" else None
		if self.userid != stored_userid:
			frappe.throw(_("Cannot change the sign-in identifier for the frappe provider."))
