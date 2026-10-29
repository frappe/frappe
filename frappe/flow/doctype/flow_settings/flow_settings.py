# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class FlowSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		search_api_key: DF.Password | None
		search_provider: DF.Literal["DuckDuckGo", "Brave", "Tavily", "Exa"]
		small_model: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if (self.search_provider or "DuckDuckGo") != "DuckDuckGo" and not self.search_api_key:
			frappe.throw(
				_("{0} needs a Search API Key.").format(self.search_provider), title=_("Missing API Key")
			)
