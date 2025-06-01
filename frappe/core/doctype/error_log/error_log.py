# Copyright (c) 2015, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document
from nts.query_builder import Interval
from nts.query_builder.functions import Now


class ErrorLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		error: DF.Code | None
		method: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.Data | None
		seen: DF.Check
		trace_id: DF.Data | None

	# end: auto-generated types
	def onload(self):
		if not self.seen and not nts.flags.read_only:
			self.db_set("seen", 1, update_modified=0)
			nts.db.commit()

	@staticmethod
	def clear_old_logs(days=30):
		table = nts.qb.DocType("Error Log")
		nts.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))


@nts.whitelist()
def clear_error_logs():
	"""Flush all Error Logs"""
	nts.only_for("System Manager")
	nts.db.truncate("Error Log")
