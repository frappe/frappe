# Copyright (c) 2013, nts and contributors
# License: MIT. See LICENSE

import nts
from nts.website.doctype.help_article.help_article import clear_cache
from nts.website.website_generator import WebsiteGenerator


class HelpCategory(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		category_description: DF.Text | None
		category_name: DF.Data
		help_articles: DF.Int
		published: DF.Check
		route: DF.Data | None
	# end: auto-generated types
	website = nts._dict(condition_field="published", page_title_field="category_name")

	def before_insert(self):
		self.published = 1

	def autoname(self):
		self.name = self.category_name

	def validate(self):
		self.set_route()

		# disable help articles of this category
		if not self.published:
			for d in nts.get_all("Help Article", dict(category=self.name)):
				nts.db.set_value("Help Article", d.name, "published", 0)

	def set_route(self):
		if not self.route:
			self.route = "kb/" + self.scrub(self.category_name)

	def on_update(self):
		clear_cache()
