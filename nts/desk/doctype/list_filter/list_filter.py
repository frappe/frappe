# Copyright (c) 2018, nts Technologies and contributors
# License: MIT. See LICENSE

from nts.model.document import Document


class ListFilter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		filter_name: DF.Data | None
		filters: DF.LongText | None
		for_user: DF.Link | None
		reference_doctype: DF.Link | None
	# end: auto-generated types
	pass
