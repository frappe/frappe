# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class OAuthBearerToken(Document):
	def validate(self):
		if not self.expiration_time:
			self.expiration_time = self.creation + frappe.utils.datetime.timedelta(seconds=self.expires_in)
