# Copyright (c) 2019, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document


class CommunicationLink(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		link_doctype: DF.Link
		link_name: DF.DynamicLink
		link_title: DF.ReadOnly | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types
	pass


def on_doctype_update():
	nts.db.add_index("Communication Link", ["link_doctype", "link_name"])
