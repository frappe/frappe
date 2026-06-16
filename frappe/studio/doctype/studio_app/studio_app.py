# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import json
import os

import frappe
from frappe import _
from frappe.utils import get_files_path
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.website_generator import WebsiteGenerator

from studio.export import can_export, delete_folder, remove_null_fields, write_document_file


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

		studio_app = frappe.db.get_value("Studio App", dict(route=app_route), "name")
		if not studio_app:
			return None
		if self.is_preview():
			return studio_app
		has_published_pages = frappe.db.exists("Studio Page", dict(studio_app=studio_app, published=1))
		return studio_app if has_published_pages else None

	def update_context(self):
		super().update_context()
		if self.is_preview():
			self.context.is_preview = True
			self.context.app_route = f"dev/{self.context.app_route}"
			self.context.template = "templates/generators/studio_renderer.html"
			self.context.app_pages = frappe.get_all(
				"Studio Page", dict(studio_app=self.context.app_name), ["name", "page_title", "route"]
			)
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
		context.frappe_app = self.frappe_app or ""
		context.base_url = frappe.utils.get_url(self.route)
		context.app_pages = frappe.get_all(
			"Studio Page", dict(studio_app=self.name, published=1), ["name", "page_title", "route"]
		)
		context.is_developer_mode = frappe.utils.cint(frappe.conf.developer_mode)
		context.site_name = frappe.local.site
		context.vite_dev_server_port = get_vite_dev_server_port()

	def autoname(self):
		if not self.name:
			self.name = self.app_name or self.app_title.lower().replace(" ", "-")

	@property
	def is_published(self):
		return frappe.db.exists("Studio Page", dict(studio_app=self.name, published=1))

	@property
	def pages(self):
		return frappe.get_all("Studio Page", filters={"studio_app": self.name}, pluck="name")

	@property
	def standard_pages(self):
		return frappe.get_all(
			"Studio Page", filters={"studio_app": self.name, "is_standard": 1}, pluck="name"
		)

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

	def before_export(self, doc):
		remove_null_fields(doc)

	def on_trash(self):
		for page in self.pages:
			frappe.delete_doc("Studio Page", page, force=True)

		if can_export(self):
			self.delete_app_folder()

	def delete_app_folder(self):
		path = self.get_folder_path()
		delete_folder(path)

	def after_rename(self, old, new, merge=False):
		if not can_export(self):
			return

		self.export_app()
		old_path = self.get_folder_path(old)
		delete_folder(old_path)

	@frappe.whitelist()
	def generate_app_build(self):
		if not frappe.has_permission("Studio App", ptype="write"):
			frappe.throw(_("You do not have permission to generate the app build"), frappe.PermissionError)

		from studio.build import StudioAppBuilder

		try:
			StudioAppBuilder(
				studio_app=self.name, is_standard=self.is_standard, frappe_app=self.frappe_app
			).build()
		except Exception as e:
			raise Exception(f"Build process failed: {str(e)}")

	@frappe.whitelist()
	def publish_app(self):
		pages = self.pages
		for page in pages:
			page_doc = frappe.get_doc("Studio Page", page)
			page_doc.publish()

		try:
			self.generate_app_build()
		except Exception:
			pass

		return {"published_pages": len(pages)}

	@frappe.whitelist()
	def unpublish_app(self):
		for page in self.pages:
			page_doc = frappe.get_doc("Studio Page", page)
			page_doc.unpublish()

	def get_assets_from_manifest(self):
		"""
		Read the Vite manifest file for this app and return asset paths
		https://vite.dev/guide/backend-integration.html#backend-integration
		"""
		try:
			if self.is_standard:
				manifest_path = os.path.join(
					frappe.get_app_path(self.frappe_app),
					"public",
					"app_builds",
					self.name,
					".vite",
					"manifest.json",
				)
				base_path = f"/assets/{self.frappe_app}/app_builds/{self.name}/"
			else:
				manifest_path = os.path.join(
					get_files_path("app_builds", self.name),
					".vite",
					"manifest.json",
				)
				base_path = f"/files/app_builds/{self.name}/"

			if not os.path.exists(manifest_path):
				return None

			with open(manifest_path) as f:
				manifest = json.load(f)

			# find the entry point for a studio app
			entry_key = f"renderer-{self.name}.js"
			entry_key = next((key for key in manifest if key.endswith(entry_key)), entry_key)

			entry = manifest[entry_key]
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

		for page_name in self.standard_pages:
			frappe.get_doc("Studio Page", page_name).export_script_to_file()

	@frappe.whitelist()
	def disable_app_export(self):
		for page_name in self.standard_pages:
			frappe.get_doc("Studio Page", page_name).restore_script_from_file()

		frappe.db.set_value("Studio Page", {"studio_app": self.name}, "is_standard", 0)

		self.is_standard = 0
		self.save()

	def export_app(self):
		if not can_export(self):
			return

		if not self.frappe_app:
			frappe.throw(_("Frappe App must be set to export the Studio App."))

		app_path = self.create_app_folder()
		self.export_studio_pages(app_path)
		self.add_to_studio_apps_txt()

	def create_app_folder(self) -> str:
		app_path = self.get_folder_path()
		frappe.create_folder(app_path)
		write_document_file(self, folder=app_path)
		self.write_tsconfig(app_path)
		return app_path

	def write_tsconfig(self, app_path: str) -> None:
		"""Let editors resolve the `@app/` alias (studio-app root) for go-to-definition etc.
		Mirrors the `studioRootAlias` vite plugin used by the dev server and per-app build."""
		tsconfig = {
			"compilerOptions": {
				"baseUrl": ".",
				"paths": {"@app/*": ["./*"]},
				# studio modules are .js/.ts — allowJs lets editors resolve both
				"allowJs": True,
				"module": "esnext",
				"moduleResolution": "node",
				"esModuleInterop": True,
				"allowSyntheticDefaultImports": True,
			},
		}
		with open(os.path.join(app_path, "tsconfig.json"), "w") as f:
			f.write(json.dumps(tsconfig, indent="\t"))
			f.write("\n")

	def export_studio_pages(self, app_path):
		page_folder_path = os.path.join(app_path, "studio_page")
		frappe.create_folder(page_folder_path)

		for page in self.pages:
			page_doc = frappe.get_doc("Studio Page", page)
			page_doc.export_page()

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


def get_vite_dev_server_port():
	port_offset = frappe.conf.webserver_port - 8000
	return 8080 + port_offset
