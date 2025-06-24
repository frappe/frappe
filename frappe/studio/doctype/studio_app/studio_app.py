# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os
import subprocess

import frappe
from frappe.model.document import Document
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.website_generator import WebsiteGenerator

from studio.api import get_app_components
from studio.utils import camel_case_to_kebab_case


class StudioAppRenderer(DocumentPage):
	def can_render(self):
		if app := self.find_app_for_path():
			self.doctype = "Studio App"
			self.docname = app
			return True

		return False

	def find_app_for_path(self):
		app_route = self.path.split("/")[0]
		return frappe.db.get_value("Studio App", dict(route=app_route), "name")


class StudioApp(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_home: DF.Link | None
		app_name: DF.Data | None
		app_title: DF.Data | None
		published: DF.Check
		route: DF.Data | None
	# end: auto-generated types

	website = frappe._dict(
		template="templates/generators/renderer.html",
		page_title_field="app_title",
		condition_field="published",
	)

	def get_context(self, context):
		csrf_token = frappe.sessions.get_csrf_token()
		frappe.db.commit()
		context.csrf_token = csrf_token
		context.no_cache = 1

		context.app_name = self.name
		context.app_route = self.route
		context.app_title = self.app_title
		context.base_url = frappe.utils.get_url(self.route)
		context.app_pages = self.get_studio_pages()
		context.is_developer_mode = frappe.conf.developer_mode
		context.site_name = frappe.local.site

	def autoname(self):
		if not self.name:
			self.name = f"app-{frappe.generate_hash(length=8)}"

	def before_insert(self):
		if not self.app_title:
			self.app_title = "My App"
		if not self.route:
			self.route = f"{camel_case_to_kebab_case(self.app_title, True)}-{frappe.generate_hash(length=4)}"

	def get_studio_pages(self):
		return frappe.get_all(
			"Studio Page", dict(studio_app=self.name, published=1), ["name", "page_title", "route"]
		)

	@frappe.whitelist()
	def generate_app_build(self):
		if not frappe.has_permission("Studio App", ptype="write"):
			frappe.throw("You do not have permission to generate the app build", frappe.PermissionError)

		try:
			components = get_app_components(self.name)
			command = f"yarn build-studio-app {self.name} --components {','.join(components)}"
			studio_app_path = frappe.get_app_source_path("studio")
			frappe.commands.popen(command, cwd=studio_app_path, raise_err=True)
		except Exception as e:
			raise Exception(f"Build process failed: {str(e)}")
