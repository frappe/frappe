# Copyright (c) 2019, nts Technologies and contributors
# License: MIT. See LICENSE

# import nts
from nts.model.document import Document


class ContactPhone(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		is_primary_mobile_no: DF.Check
		is_primary_phone: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone: DF.Data
	# end: auto-generated types
	pass
