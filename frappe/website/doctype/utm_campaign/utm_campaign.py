# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class UTMCampaign(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		campaign_description: DF.SmallText | None
		slug: DF.Data | None
	# end: auto-generated types

	def before_save(self) -> None:
		if self.slug:
			self.slug = frappe.utils.slug(self.slug)
