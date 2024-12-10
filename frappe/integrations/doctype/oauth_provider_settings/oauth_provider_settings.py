# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class OAuthProviderSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		skip_authorization: DF.Literal["Force", "Auto"]
	# end: auto-generated types
<<<<<<< HEAD
=======

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass


def get_oauth_settings():
<<<<<<< HEAD
	"""Returns oauth settings"""
=======
	"""Return OAuth settings."""
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	return frappe._dict(
		{"skip_authorization": frappe.db.get_single_value("OAuth Provider Settings", "skip_authorization")}
	)
