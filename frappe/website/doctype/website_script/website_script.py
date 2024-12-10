# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class WebsiteScript(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		javascript: DF.Code | None
<<<<<<< HEAD

	# end: auto-generated types
=======
	# end: auto-generated types

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def on_update(self):
		"""clear cache"""
		frappe.clear_cache(user="Guest")

		from frappe.website.utils import clear_cache

		clear_cache()
