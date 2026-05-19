# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import frappe
import frappe.utils
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	get_system_timezone,
	now_datetime,
	validate_email_address,
	validate_phone_number,
	validate_url,
)


class SecuritySettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.security_settings_contact.security_settings_contact import (
			SecuritySettingsContact,
		)
		from frappe.core.doctype.security_settings_language.security_settings_language import (
			SecuritySettingsLanguage,
		)
		from frappe.types import DF

		public_contacts: DF.Table[SecuritySettingsContact]
		public_expires: DF.Datetime | None
		public_languages: DF.TableMultiSelect[SecuritySettingsLanguage]
		public_policy: DF.Data | None
	# end: auto-generated types

	@property
	def security_txt(self):
		return (
			"\n\n".join(
				[
					self.public_policy_section,
					self.public_contacts_section,
					self.public_languages_section,
					self.public_expires_section,
				]
			)
			+ "\n"
		)

	@property
	def public_policy_section(self):
		value = self.public_policy or "https://frappe.io/security"
		return f"# Read our security policy before reporting an issue\nPolicy: {value}"

	@property
	def public_contacts_section(self):
		contacts = [self.with_protocol(c.contact, c.type) for c in self.public_contacts] or [
			"https://security.frappe.io"
		]
		value = "\n".join(f"Contact: {c}" for c in contacts)
		return f"# Our security address\n{value}"

	@property
	def public_languages_section(self):
		langs = [l.language for l in self.public_languages] or ["en"]
		value = ", ".join(langs)
		return f"# We prefer talking in\nPreferred-Languages: {value}"

	@property
	def public_expires_section(self):
		expires = self.public_expires or frappe.utils.add_years(frappe.utils.now_datetime(), 1)
		if isinstance(expires, str):
			expires = datetime.fromisoformat(expires)
		expires = expires.replace(microsecond=0, tzinfo=ZoneInfo(get_system_timezone())).astimezone(UTC)
		value = expires.strftime("%Y-%m-%dT%H:%M:%SZ")
		return f"Expires: {value}"

	def with_protocol(self, url: str, type_: str) -> str:
		"""Prefix the URL with the appropriate protocol based on the contact type."""
		match type_:
			case "Email":
				if not url.startswith("mailto:"):
					return f"mailto:{url}"
			case "Phone":
				if not url.startswith("tel:"):
					return f"tel:{url}"
		return url

	def validate(self):
		self.validate_public_policy()
		self.validate_public_contacts()
		self.validate_expires()

	def validate_public_policy(self):
		if self.public_policy:
			if not self.public_policy.startswith("https://"):
				frappe.throw(_("Public Policy URL must start with https://"))

	def validate_public_contacts(self):
		for contact in self.public_contacts:
			match contact.type:
				case "Email":
					validate_email_address(contact.contact, throw=True)
				case "Phone":
					validate_phone_number(contact.contact, throw=True)
				case "Website":
					validate_url(contact.contact, throw=True)
					if not contact.contact.startswith("https://"):
						frappe.throw(_("URL contact must start with https://"))

	def validate_expires(self):
		if self.public_expires:
			expires = self.public_expires
			if isinstance(expires, str):
				expires = datetime.fromisoformat(expires)
			if expires <= now_datetime():
				frappe.throw(_("Expiration date must be in the future"))
