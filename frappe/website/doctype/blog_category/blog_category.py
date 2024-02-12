# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.website.utils import clear_cache
from frappe.website.website_generator import WebsiteGenerator


class BlogCategory(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		preview_image: DF.AttachImage | None
		published: DF.Check
		route: DF.Data | None
		title: DF.Data
	# end: auto-generated types

	def autoname(self):
		# to override autoname of WebsiteGenerator
		self.name = self.scrub(self.title)

	def on_update(self):
		clear_cache()

	def set_route(self):
		# Override blog route since it has to been templated
		self.route = "blog/" + self.name
