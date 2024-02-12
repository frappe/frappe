# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class OAuthAuthorizationCode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		authorization_code: DF.Data | None
		client: DF.Link | None
		code_challenge: DF.Data | None
		code_challenge_method: DF.Literal["", "s256", "plain"]
		expiration_time: DF.Datetime | None
		nonce: DF.Data | None
		redirect_uri_bound_to_authorization_code: DF.Data | None
		scopes: DF.Text | None
		user: DF.Link | None
		validity: DF.Literal["Valid", "Invalid"]
	# end: auto-generated types

	pass
