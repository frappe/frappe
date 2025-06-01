# Copyright (c) 2019, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document
from nts.query_builder import Interval
from nts.query_builder.functions import Now


class ScheduledJobLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		debug_log: DF.Code | None
		details: DF.Code | None
		scheduled_job_type: DF.Link
		status: DF.Literal["Scheduled", "Complete", "Failed"]

	# end: auto-generated types
	@staticmethod
	def clear_old_logs(days=90):
		table = nts.qb.DocType("Scheduled Job Log")
		nts.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
