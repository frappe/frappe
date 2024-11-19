# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SamlLoginKey(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		acs_url: DF.Data | None
		audience_uri: DF.Data | None
		certificate: DF.Text | None
		enable_saml_login: DF.Check
		provider_name: DF.Data | None
		sp_entity_id: DF.Data | None
		sso_url: DF.Data | None
	# end: auto-generated types
	pass
