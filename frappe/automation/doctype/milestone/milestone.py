# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class Milestone(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		milestone_tracker: DF.Link | None
		reference_name: DF.Data
		reference_type: DF.Link
		track_field: DF.Data
		value: DF.Data
	# end: auto-generated types

	pass


def on_doctype_update():
	frappe.db.add_index("Milestone", ["reference_type", "reference_name"])
