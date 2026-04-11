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

	@property
	def security_txt(self):
		[[policy, contact, preferred_language]] = frappe.db.get_values(
			"Security Settings", fieldname=["public_policy", "public_contact", "public_language"]
		)
		policy = policy or self.default_public_policy
		contact = contact or self.default_public_contact
		preferred_language = preferred_language or self.default_public_language
		return (
			"# Read our security policy before reporting an issue\n"
			f"Policy: {policy}\n\n"
			"# Our security address\n"
			f"Contact: {contact}\n\n"
			"# We prefer talking in\n"
			f"Preferred-Languages: {preferred_language}"
		)

	@property
	def default_public_policy(self):
		return "https://frappe.io/security"

	@property
	def default_public_contact(self):
		return "https://security.frappe.io"

	@property
	def default_public_language(self):
		return "en"

	def validate(self):
		self.validate_public_policy()

	def validate_public_policy(self):
		if self.public_policy:
			if not self.public_policy.startswith("https://"):
				frappe.throw("Public Policy URL must start with https://")
