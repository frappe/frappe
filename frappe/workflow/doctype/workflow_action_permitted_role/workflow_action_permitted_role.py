# Copyright (c) 2022, nts Technologies and contributors
# For license information, please see license.txt

# import nts
from nts.model.document import Document


class WorkflowActionPermittedRole(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		role: DF.Link | None
	# end: auto-generated types
	pass
