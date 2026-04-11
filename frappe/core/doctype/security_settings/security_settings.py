# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SecuritySettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		public_contact: DF.Data | None
		public_language: DF.Data | None
		public_policy: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.validate_public_policy()

	def validate_public_policy(self):
		if self.public_policy:
			if not self.public_policy.startswith("https://"):
				frappe.throw("Public Policy URL must start with https://")
