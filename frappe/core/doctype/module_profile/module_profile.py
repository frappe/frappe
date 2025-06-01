# Copyright (c) 2020, nts Technologies and contributors
# License: MIT. See LICENSE

from nts.model.document import Document


class ModuleProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.core.doctype.block_module.block_module import BlockModule
		from nts.types import DF

		block_modules: DF.Table[BlockModule]
		module_profile_name: DF.Data

	# end: auto-generated types
	def onload(self):
		from nts.config import get_modules_from_all_apps

		self.set_onload("all_modules", sorted(m.get("module_name") for m in get_modules_from_all_apps()))
