# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _, qb
from frappe.model.document import Document
from frappe.utils.data import comma_and


class DuckDBDashboard(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.duckdb_sync_item.duckdb_sync_item import DuckDBSyncItem
		from frappe.types import DF

		doctype_to_sync: DF.Table[DuckDBSyncItem]
	# end: auto-generated types

	def get_modified_and_new_rows(self):
		old_doc = self.get_doc_before_save()
		old = set([x.doc_type for x in old_doc.doctype_to_sync])
		new = set([x.doc_type for x in self.doctype_to_sync])
		return list(new - old)

	def validate_invalid_selection(self):
		if new_rows := self.get_modified_and_new_rows():
			dt = qb.DocType("DocType")
			if (
				res := qb.from_(dt)
				.select(dt.name)
				.where((dt.name.isin(new_rows)) & (dt.issingle.eq(True) | dt.is_virtual.eq(True)))
				.run(as_list=True, pluck="name")
			):
				frappe.throw(
					msg=_("Single or Virtual doctypes can't bs synced to DuckDB: {0}").format(
						frappe.bold(comma_and(res))
					),
					title="Invalid doctype selection",
				)

	def validate_duplicate(self):
		uniq = Counter(set([x.doc_type for x in self.doctype_to_sync]))
		new_rows = Counter([x.doc_type for x in self.doctype_to_sync])
		if duplicates := (new_rows - uniq):
			duplicates = [x for x in duplicates.keys()]
			frappe.throw(
				msg=_("{0} selected multiple times.").format(frappe.bold(comma_and(duplicates, False))),
				title="Duplicate doctype selection",
			)

	def validate(self):
		self.validate_invalid_selection()
		self.validate_duplicate()
