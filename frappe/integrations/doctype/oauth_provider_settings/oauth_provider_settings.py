# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class OAuthProviderSettings(Document):
	pass


def get_oauth_settings():
	"""Returns oauth settings"""
	out = frappe._dict(
		{
			"skip_authorization": frappe.db.get_single_value(
				"OAuth Provider Settings", "skip_authorization"
			)
		}
	)

	return out
