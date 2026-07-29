# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MapReduceTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		key: DF.Data | None
		map: DF.Data | None
		map_partial: DF.JSON | None
		master: DF.Link | None
		name: DF.Int | None
		reduce: DF.Data | None
		status: DF.Literal["Queued", "Running", "Completed"]
		value: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "MapReduce Task"
