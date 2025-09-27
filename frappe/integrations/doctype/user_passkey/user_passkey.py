# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class UserPasskey(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		credential_id: DF.Data | None
		public_key: DF.SmallText | None
		sign_count: DF.Int
		status: DF.Literal["", "Active", "Revoked"]
		title: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	pass
