# Copyright (c) 2017, nts Technologies and contributors
# License: MIT. See LICENSE

# import nts
from nts.model.document import Document


class WebhookHeader(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		key: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		value: DF.Data | None
	# end: auto-generated types
	pass
