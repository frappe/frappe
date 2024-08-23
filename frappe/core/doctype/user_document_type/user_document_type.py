# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class UserDocumentType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amend: DF.Check
		cancel: DF.Check
		create: DF.Check
		delete: DF.Check
		document_type: DF.Link
		email: DF.Check
		is_custom: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		print: DF.Check
		read: DF.Check
		share: DF.Check
		submit: DF.Check
		write: DF.Check
	# end: auto-generated types

	pass
