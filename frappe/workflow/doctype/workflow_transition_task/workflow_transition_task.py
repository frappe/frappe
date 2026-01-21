# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkflowTransitionTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		asynchronous: DF.Check
		email_template: DF.Link | None
		enabled: DF.Check
		link: DF.DynamicLink | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		receiver_by_document_field: DF.Data | None
		task: DF.Literal[None]
	# end: auto-generated types

	pass
