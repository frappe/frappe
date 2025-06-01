# Copyright (c) 2021, nts Technologies and contributors
# License: MIT. See LICENSE

# import nts
from nts.model.document import Document


class UserGroupMember(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		user: DF.Link
	# end: auto-generated types
	pass
