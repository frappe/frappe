# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document


class TopBarItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		label: DF.Data
		open_in_new_tab: DF.Check
		parent: DF.Data
		parent_label: DF.Literal[None]
		parentfield: DF.Data
		parenttype: DF.Data
		right: DF.Check
		url: DF.Data | None
	# end: auto-generated types

	pass
