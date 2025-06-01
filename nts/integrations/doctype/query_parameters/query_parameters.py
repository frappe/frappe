# Copyright (c) 2020, nts Technologies and contributors
# License: MIT. See LICENSE

# import nts
from nts.model.document import Document


class QueryParameters(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		key: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		value: DF.Data
	# end: auto-generated types
	pass
