# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OAuthSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allowed_public_client_origins: DF.SmallText | None
		enable_dynamic_client_registration: DF.Check
		resource_documentation: DF.Data | None
		resource_name: DF.Data | None
		resource_policy_uri: DF.Data | None
		resource_tos_uri: DF.Data | None
		scopes_supported: DF.SmallText | None
		show_auth_server_metadata: DF.Check
		show_protected_resource_metadata: DF.Check
		show_social_login_key_as_authorization_server: DF.Check
		skip_authorization: DF.Check
	# end: auto-generated types

	pass
