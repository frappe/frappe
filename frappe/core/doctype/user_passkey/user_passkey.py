# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class UserPasskey(Document):
	_DOCTYPE_NAME = "User Passkey"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		backed_up: DF.Check
		credential_id: DF.Data
		label: DF.Data
		last_used: DF.Datetime | None
		multi_device: DF.Check
		public_key: DF.Password
		rp_id: DF.Data
		sign_count: DF.LongInt
		transports: DF.Data | None
		user: DF.Link
	# end: auto-generated types

	def before_insert(self):
		self.owner = self.user
