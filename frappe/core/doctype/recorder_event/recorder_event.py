# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RecorderEvent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		apps: DF.Data | None
		depth: DF.Int
		duration: DF.Float
		handlers: DF.SmallText | None
		label: DF.Data | None
		method: DF.Data | None
		queries: DF.Int
		ref_doctype: DF.Data | None
		ref_name: DF.Data | None
		seq: DF.Int
	# end: auto-generated types

	pass
