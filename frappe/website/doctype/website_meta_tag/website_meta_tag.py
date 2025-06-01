# Copyright (c) 2019, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document


class WebsiteMetaTag(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		key: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		value: DF.Text

	# end: auto-generated types
	def get_content(self):
		# can't have new lines in meta content
		return (self.value or "").replace("\n", " ")

	def get_meta_dict(self):
		return {self.key: self.get_content()}

	def set_in_context(self, context):
		context.setdefault("metatags", nts._dict({}))
		context.metatags[self.key] = self.get_content()
		return context
