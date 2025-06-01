# Copyright (c) 2018, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document


class ViewLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		viewed_by: DF.Data | None

	# end: auto-generated types
	@staticmethod
	def clear_old_logs(days=180):
		from nts.query_builder import Interval
		from nts.query_builder.functions import Now

		table = nts.qb.DocType("View Log")
		nts.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
