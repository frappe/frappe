# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ProposableDoctype(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.proposable_doctype_item.proposable_doctype_item import (
			ProposableDoctypeItem,
		)
		from frappe.types import DF

		proposable_doctypes: DF.Table[ProposableDoctypeItem]
	# end: auto-generated types
	pass
