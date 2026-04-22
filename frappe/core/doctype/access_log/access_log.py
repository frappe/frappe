# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt

import frappe
from frappe.model.document import Document
from frappe.utils import cstr


class AccessLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		columns: DF.HTMLEditor | None
		export_from: DF.Data | None
		file_type: DF.Data | None
		filters: DF.Code | None
		method: DF.Data | None
		page: DF.HTMLEditor | None
		reference_document: DF.Data | None
		report_name: DF.Data | None
		timestamp: DF.Datetime | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Access Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
@frappe.write_only()
@retry(
	stop=stop_after_attempt(3),
	retry=retry_if_exception_type(frappe.DuplicateEntryError),
	reraise=True,
)
def make_access_log(
	doctype: str | None = None,
	document: str | int | None = None,
	method: str | None = None,
	file_type: str | None = None,
	report_name: str | None = None,
	filters: str | list | dict[str, Any] | None = None,
	page: str | None = None,
	columns: str | None = None,
):
	access_log = frappe.get_doc(
		{
			"doctype": "Access Log",
			"user": frappe.session.user,
			"export_from": doctype,
			"reference_document": document,
			"file_type": file_type,
			"report_name": report_name,
			"page": page,
			"method": method,
			"filters": cstr(filters) or None,
			"columns": columns,
		}
	)

	if not frappe.in_test:
		access_log.deferred_insert()
	else:
		access_log.db_insert()


# only for backward compatibility
_make_access_log = make_access_log
