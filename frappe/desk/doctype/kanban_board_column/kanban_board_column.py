# Copyright (c) 2015, nts Technologies and contributors
# License: MIT. See LICENSE

from nts.model.document import Document


class KanbanBoardColumn(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		column_name: DF.Data | None
		indicator: DF.Literal[
			"Blue",
			"Cyan",
			"Gray",
			"Green",
			"Light Blue",
			"Orange",
			"Pink",
			"Purple",
			"Red",
			"Red",
			"Yellow",
		]
		order: DF.Code | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		status: DF.Literal["Active", "Archived"]
	# end: auto-generated types
	pass
