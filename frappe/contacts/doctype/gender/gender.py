# Copyright (c) 2017, nts Technologies and contributors
# License: MIT. See LICENSE

from nts.model.document import Document


class Gender(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		gender: DF.Data | None
	# end: auto-generated types
	pass
