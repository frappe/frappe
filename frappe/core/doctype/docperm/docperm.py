# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class DocPerm(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amend: DF.Check
		cancel: DF.Check
		create: DF.Check
		delete: DF.Check
		email: DF.Check
		export: DF.Check
		if_owner: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		permlevel: DF.Int
		print: DF.Check
		read: DF.Check
		report: DF.Check
		role: DF.Link
		select: DF.Check
		share: DF.Check
		submit: DF.Check
		write: DF.Check
	# end: auto-generated types

	pass
