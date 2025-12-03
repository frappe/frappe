# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.security.content_security_policy import csp_validator


class SecuritySettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.security.doctype.content_security_policy_directive.content_security_policy_directive import (
			ContentSecurityPolicyDirective,
		)
		from frappe.types import DF

		csp_directives: DF.Table[ContentSecurityPolicyDirective]
		csp_enable_reporting: DF.Check
		csp_enabled: DF.Check
		csp_reporting_only: DF.Check
		csp_reporting_url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		csp_validator.check(self.csp_directives)

	def on_update(self):
		clear_cache()


def get_security_settings(key: str):
	if not (settings := getattr(frappe.local, "security_settings", None)):
		settings = frappe.client_cache.get_doc("Security Settings")
		frappe.local.security_settings = settings
	return settings.get(key)


def clear_cache():
	frappe.client_cache.delete_value(frappe.get_document_cache_key("Security Settings", "Security Settings"))
	frappe.cache.delete_value("security_settings")
