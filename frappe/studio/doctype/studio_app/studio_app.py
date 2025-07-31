# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import json
import os

import frappe
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.website_generator import WebsiteGenerator

from studio.api import get_app_components
from studio.export import delete_folder, write_document_file


class StudioAppRenderer(DocumentPage):
	def can_render(self):
		if app := self.find_app_for_path():
			self.doctype = "Studio App"
			self.docname = app
			return True

		return False

	def find_app_for_path(self):
		_path = self.path.split("/")
		if self.is_preview():
			app_route = _path[1]
		else:
			app_route = _path[0]
		return frappe.db.get_value("Studio App", dict(route=app_route), "name")

	def update_context(self):
		super().update_context()
		if self.is_preview():
			self.context.is_preview = True
			self.context.app_route = f"dev/{self.context.app_route}"
			self.context.template = "templates/generators/studio_renderer.html"
		else:
			self.context.template = "templates/generators/app_renderer.html"
			manifest = self.context.doc.get_assets_from_manifest()
			if manifest:
				self.context.stylesheets = manifest.get("stylesheets", [])
				self.context.script = manifest.get("script")
			else:
				self.context.template = "templates/generators/studio_renderer.html"
				self.context.assets_not_found = True

	def is_preview(self):
		return self.path.startswith("dev/")


class StudioApp(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_home: DF.Link | None
		app_name: DF.Data | None
		app_title: DF.Data
		frappe_app: DF.Literal[None]
		is_standard: DF.Check
		published: DF.Check
		route: DF.Data | None
	# end: auto-generated types

	website = frappe._dict(
		template="templates/generators/app_renderer.html",
		page_title_field="app_title",
		condition_field="published",
	)

	def get_context(self, context):
		csrf_token = frappe.sessions.get_csrf_token()
		frappe.db.commit()
		context.csrf_token = csrf_token
		context.no_cache = 1

		context.app_name = self.app_name
		context.app_route = self.route
		context.app_title = self.app_title
		context.base_url = frappe.utils.get_url(self.route)
		context.app_pages = self.get_studio_pages()
		context.is_developer_mode = frappe.conf.developer_mode
		context.site_name = frappe.local.site

	def autoname(self):
		if not self.name:
			self.name = self.app_name or self.app_title.lower().replace(" ", "-")

	def before_insert(self):
		if not self.app_title:
			self.app_title = "My App"
		if not self.route:
			if not self.name:
				self.autoname()
			self.route = self.name

	def on_update(self):
		self.export_app()
		if not self.flags.in_insert and self.has_value_changed("is_standard") and not self.is_standard:
			self.delete_app_folder()

	def on_trash(self):
		for page in frappe.get_all("Studio Page", filters={"studio_app": self.name}, pluck="name"):
			frappe.delete_doc("Studio Page", page, force=True)

		if self.is_standard:
			self.delete_app_folder()

	def delete_app_folder(self):
		path = self.get_folder_path()
		delete_folder(path)

	def after_rename(self, old, new, merge=False):
		self.export_app()
		old_path = self.get_folder_path(old)
		delete_folder(old_path)

	def get_studio_pages(self):
		return frappe.get_all(
			"Studio Page", dict(studio_app=self.name, published=1), ["name", "page_title", "route"]
		)

	@frappe.whitelist()
	def generate_app_build(self):
		if not frappe.has_permission("Studio App", ptype="write"):
			frappe.throw("You do not have permission to generate the app build", frappe.PermissionError)

		# check if build is required
		draft_components = get_app_components(self.name, "draft_blocks")
		components = get_app_components(self.name)
		if not draft_components.symmetric_difference(components):
			return

		try:
			command = f"yarn build-studio-app {self.name} --components {','.join(list(components))}"
			studio_app_path = frappe.get_app_source_path("studio")
			frappe.commands.popen(command, cwd=studio_app_path, raise_err=True)
		except Exception as e:
			raise Exception(f"Build process failed: {str(e)}")

	def get_assets_from_manifest(self):
		"""
		Read the Vite manifest file for this app and return asset paths
		https://vite.dev/guide/backend-integration.html#backend-integration
		"""
		try:
			manifest_path = os.path.join(
				frappe.get_app_source_path("studio"),
				"studio",
				"public",
				"app_builds",
				self.name,
				".vite",
				"manifest.json",
			)
			if not os.path.exists(manifest_path):
				return None

			with open(manifest_path) as f:
				manifest = json.load(f)

			# find the entry point for a studio app
			entry_key = f"renderer-{self.name}.js"
			entry_key = next((key for key in manifest if key.endswith(entry_key)), entry_key)

			entry = manifest[entry_key]
			base_path = f"/assets/studio/app_builds/{self.name}/"
			result = {
				"script": f"{base_path}{entry['file']}",
				"stylesheets": [f"{base_path}{css_file}" for css_file in entry.get("css", [])],
			}

			# add any imported CSS files
			for chunk_key, chunk_data in manifest.items():
				if chunk_key != entry_key and "css" in chunk_data:
					result["stylesheets"].extend(f"{base_path}{css_file}" for css_file in chunk_data["css"])

			return result

		except Exception as e:
			frappe.log_error(f"Error reading manifest for app {self.name}: {str(e)}")
			return None

	@frappe.whitelist()
	def enable_app_export(self, target_app: str):
		frappe.db.set_value(
			"Studio Page",
			{"studio_app": self.name},
			{
				"is_standard": 1,
				"frappe_app": target_app,
			},
		)

		self.is_standard = 1
		self.frappe_app = target_app
		self.save()

	@frappe.whitelist()
	def disable_app_export(self):
		frappe.db.set_value("Studio Page", {"studio_app": self.name}, "is_standard", 0)

		self.is_standard = 0
		self.save()

	def export_app(self):
		if frappe.flags.in_import or not frappe.conf.developer_mode or not self.is_standard:
			return

		if not self.frappe_app:
			frappe.throw("Frappe App must be set to export the Studio App.")

		app_path = self.create_app_folder()
		self.export_studio_pages(app_path)
		self.add_to_studio_apps_txt()

	def create_app_folder(self) -> str:
		app_path = self.get_folder_path()
		frappe.create_folder(app_path, with_init=True)
		write_document_file(self, folder=app_path)
		return app_path

	def export_studio_pages(self, app_path):
		page_folder_path = os.path.join(app_path, "studio_page")
		frappe.create_folder(page_folder_path, with_init=True)

		for page in frappe.get_all(
			"Studio Page", filters={"studio_app": self.name, "is_standard": 1}, pluck="name"
		):
			page_doc = frappe.get_doc("Studio Page", page)
			write_document_file(page_doc, folder=page_folder_path)

	def add_to_studio_apps_txt(self):
		if self.frappe_app != "studio":
			return

		apps = None
		app_folder_name = frappe.scrub(self.name)
		with open(frappe.get_app_path("studio", "studio_apps.txt")) as f:
			content = f.read()
			if app_folder_name not in content.splitlines():
				apps = list(filter(None, content.splitlines()))
				apps.append(app_folder_name)

			if apps:
				with open(frappe.get_app_path("studio", "studio_apps.txt"), "w") as f:
					f.write("\n".join(apps))

	def get_folder_path(self, name: str | None = None):
		return frappe.get_app_source_path(self.frappe_app, "studio", name or self.name)
