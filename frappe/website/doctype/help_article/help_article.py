# Copyright (c) 2013, Frappe and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, is_markdown, markdown
from frappe.website.utils import get_comment_list
from frappe.website.website_generator import WebsiteGenerator


class HelpArticle(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		author: DF.Data | None
		category: DF.Link
		content: DF.TextEditor
		helpful: DF.Int
		level: DF.Literal["Beginner", "Intermediate", "Expert"]
		likes: DF.Int
		not_helpful: DF.Int
		published: DF.Check
		route: DF.Data | None
		title: DF.Data
	# end: auto-generated types

	def validate(self) -> None:
		self.set_route()

	def set_route(self) -> None:
		"""Set route from category and title if missing"""
		if not self.route:
			self.route = "/".join(
				[frappe.get_value("Help Category", self.category, "route"), self.scrub(self.title)]
			)

	def on_update(self) -> None:
		self.update_category()

	def clear_cache(self):
		clear_knowledge_base_cache()
		return super().clear_cache()

	def update_category(self) -> None:
		cnt = frappe.db.count("Help Article", filters={"category": self.category, "published": 1})
		cat = frappe.get_doc("Help Category", self.category)
		cat.help_articles = cnt
		cat.save()

	def get_context(self, context) -> None:
		if is_markdown(context.content):
			context.content = markdown(context.content)
		context.login_required = True
		context.category = frappe.get_doc("Help Category", self.category)
		context.level_class = get_level_class(self.level)
		context.comment_list = get_comment_list(self.doctype, self.name)
		context.show_sidebar = True
		context.sidebar_items = get_sidebar_items()
		context.parents = self.get_parents(context)

	def get_parents(self, context):
		return [{"title": context.category.category_name, "route": context.category.route}]


def get_list_context(context=None):
	filters = dict(published=1)

	category = frappe.db.get_value("Help Category", {"route": frappe.local.path})

	if category:
		filters["category"] = category

	list_context = frappe._dict(
		title=category or _("Knowledge Base"),
		get_level_class=get_level_class,
		show_sidebar=True,
		sidebar_items=get_sidebar_items(),
		hide_filters=True,
		filters=filters,
		category=frappe.local.form_dict.category,
		no_breadcrumbs=True,
	)

	if frappe.local.form_dict.txt:
		list_context.blog_subtitle = _('Filtered by "{0}"').format(frappe.local.form_dict.txt)
	#
	# list_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
	return list_context


def get_level_class(level):
	return {"Beginner": "green", "Intermediate": "orange", "Expert": "red"}[level]


def get_sidebar_items():
	def _get():
		return frappe.db.sql(
			"""select
				concat(category_name, " (", help_articles, ")") as title,
				concat('/', route) as route
			from
				`tabHelp Category`
			where
				published = 1 and help_articles > 0
			order by
				help_articles desc""",
			as_dict=True,
		)

	return frappe.cache.get_value("knowledge_base:category_sidebar", _get)


def clear_knowledge_base_cache() -> None:
	frappe.cache.delete_value("knowledge_base:category_sidebar")
	frappe.cache.delete_value("knowledge_base:faq")


@frappe.whitelist(allow_guest=True)
@rate_limit(key="article", limit=5, seconds=60 * 60)
def add_feedback(article: str, helpful: str) -> None:
	field = "not_helpful" if helpful == "No" else "helpful"

	value = cint(frappe.db.get_value("Help Article", article, field))
	frappe.db.set_value("Help Article", article, field, value + 1, update_modified=False)
