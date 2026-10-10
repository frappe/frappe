# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import json
import os
import re
import shutil
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_files_path
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.website_generator import WebsiteGenerator

from studio.export import can_export, delete_file, delete_folder, write_document_file
from studio.realtime import publish_doc_change
from studio.utils import walk_blocks

APP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
IMPORT_RE = re.compile(r"""(?:from|import)\s*\(?\s*['"]((?:@app/|\.\.?/)[^'"]+)['"]""")
EXTENSIONS = (".ts", ".js", ".vue", ".json", ".css")


class StudioAppRenderer(DocumentPage):
	def render(self):
		# redirect guests to login instead of serving a dead page.
		if frappe.session.user == "Guest" and not self.can_render_for_guest():
			frappe.flags.redirect_location = f"/login?redirect-to=/{quote(self.path)}"
			raise frappe.Redirect(http_status_code=302)
		return super().render()

	def can_render_for_guest(self):
		if self.is_preview():
			return False
		return bool(
			frappe.db.exists("Studio Page", dict(studio_app=self.docname, published=1, allow_guest=1))
		)

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
		favicon: DF.AttachImage | None
		frappe_app: DF.Literal[None]
		is_standard: DF.Check
		route: DF.Data | None
		router_script: DF.Code | None
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
		context.app_home = self.app_home
		context.favicon = self.favicon
		context.frappe_app = self.frappe_app or ""
		context.is_guest = frappe.session.user == "Guest"
		page_filters = dict(studio_app=self.name, published=1)
		if context.is_guest:
			page_filters["allow_guest"] = 1
		context.app_pages = frappe.get_all("Studio Page", page_filters, ["name", "page_title", "route"])

		context.is_developer_mode = frappe.utils.cint(frappe.conf.developer_mode)
		context.router_file = self.get_router_file() if context.is_developer_mode else None
		context.router_script = self.get_router_script()

		context.base_url = frappe.utils.get_url(self.route)
		context.boot = self.get_boot()
		context.vite_dev_server_host = get_vite_dev_server_host()

	def get_router_file(self) -> str | None:
		if not (self.is_standard and self.frappe_app):
			return None
		from studio.build import get_router_file

		return get_router_file(self.frappe_app, self.name)

	def get_router_script(self) -> str | None:
		"""A custom app's router config, kept in the DB; a standard app has it in router.ts"""
		if self.is_standard:
			return None
		return self.router_script or None

	def get_boot(self) -> dict:
		"""Get the boot data for this Studio app"""
		handlers = frappe.get_hooks("studio_app_boot", {}).get(self.name) or []
		if not handlers:
			return {}
		try:
			return frappe.get_attr(handlers[-1])() or {}
		except Exception:
			frappe.log_error(title=f"studio_app_boot failed for {self.name}")
			return {}

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
		publish_doc_change("Studio App", self.name, self.name)

	def on_trash(self):
		for page in self.pages:
			frappe.delete_doc("Studio Page", page, force=True)

		if can_export(self):
			self.delete_app_folder()

	def delete_app_folder(self):
		path = self.get_folder_path()
		delete_folder(path)

	@frappe.whitelist()
	def rename_app(self, new_name: str) -> dict:
		"""Rename the app (its docname and app_name). Built assets carry the old name in their
		URLs, so `stale_build` tells the caller the app needs a rebuild to serve the build again."""
		if not APP_NAME_RE.match(new_name or ""):
			frappe.throw(_("App Name can only have lowercase letters, numbers, hyphens and underscores."))
		had_build = bool(self.get_assets_from_manifest())
		new_name = frappe.rename_doc("Studio App", self.name, new_name)
		return {"name": new_name, "stale_build": had_build}

	def before_rename(self, old, new, merge=False):
		if self.is_standard and not can_export(self):
			frappe.throw(_("Exported apps can only be renamed in developer mode."))
		if can_export(self) and os.path.exists(self.get_folder_path(new)):
			frappe.throw(_("Folder {0} already exists.").format(self.get_folder_path(new)))

	def after_rename(self, old, new, merge=False):
		if not can_export(self):
			return

		# carry every exported file (page scripts, router.ts, components) over to the new folder
		move_folder(self.get_folder_path(old), self.get_folder_path())
		try:
			self.export_app()
		except Exception:
			self.undo_rename_export(old)
			raise
		delete_file(self.get_folder_path(), f"{frappe.scrub(old)}.json")
		self.remove_from_studio_apps_txt(old)

	def undo_rename_export(self, old: str):
		"""The DB rolls back a failed rename but the folder move doesn't, so put it back."""
		delete_file(self.get_folder_path(), f"{frappe.scrub(self.name)}.json")
		self.remove_from_studio_apps_txt(self.name)
		move_folder(self.get_folder_path(), self.get_folder_path(old))

	def move_export_to(self, target_app: str):
		"""Carry the export folder, files and all, into another Frappe app. Exported page scripts
		and router.ts live only in these files, so re-exporting from the DB would lose them."""
		old_path = self.get_folder_path()
		new_path = self.get_folder_path(frappe_app=target_app)
		if os.path.exists(new_path):
			frappe.throw(_("Folder {0} already exists.").format(new_path))
		self.remove_from_studio_apps_txt(self.name)
		move_folder(old_path, new_path)

	def undo_export_move(self, previous_app: str, target_app: str):
		"""The DB rolls back a failed move but the folder move doesn't, so carry it back."""
		self.frappe_app = target_app
		self.remove_from_studio_apps_txt(self.name)
		move_folder(self.get_folder_path(), self.get_folder_path(frappe_app=previous_app))
		self.frappe_app = previous_app
		self.add_to_studio_apps_txt()

	@frappe.whitelist()
	def generate_app_build(self) -> dict:
		"""Build the app bundle. Failures are logged to an Error Log and returned as
		`build_error` instead of raised, so callers can surface them in the UI."""
		if not frappe.has_permission("Studio App", ptype="write"):
			frappe.throw(_("You do not have permission to generate the app build"), frappe.PermissionError)

		try:
			self.build_app_bundle()
			return {"build_error": None}
		except Exception as e:
			return {"build_error": self._log_build_failure(e)}

	def build_app_bundle(self):
		"""Build the app bundle, raising on failure — background jobs enqueue this
		so a failed build marks the job as failed instead of looking successful."""
		from studio.build import StudioAppBuilder

		StudioAppBuilder(
			studio_app=self.name, is_standard=self.is_standard, frappe_app=self.frappe_app
		).build()

	def _log_build_failure(self, exception: Exception) -> dict:
		error_log = frappe.log_error(
			title=f"Studio app build failed: {self.name}",
			message=getattr(exception, "output", None) or frappe.get_traceback(),
		)
		return {"error_log": error_log.name}

	@frappe.whitelist()
	def publish_app(self):
		pages = self.pages
		for page in pages:
			page_doc = frappe.get_doc("Studio Page", page)
			page_doc.publish()

		return {"published_pages": len(pages), **self.generate_app_build()}

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
		previous_app = self.frappe_app if self.is_standard else None
		if not previous_app or previous_app == target_app:
			return self.save_export_settings(target_app)

		self.move_export_to(target_app)
		try:
			self.save_export_settings(target_app)
		except Exception:
			self.undo_export_move(previous_app, target_app)
			raise

	def save_export_settings(self, target_app: str):
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
		self.export_router_script_to_file()

	@frappe.whitelist()
	def disable_app_export(self) -> str | None:
		"""Returns a notice for the user when router.ts was copied back, since it may not run as a script"""
		for page_name in self.standard_pages:
			frappe.get_doc("Studio Page", page_name).restore_script_from_file()
		router_restored = self.restore_router_script_from_file()

		frappe.db.set_value("Studio Page", {"studio_app": self.name}, "is_standard", 0)

		self.is_standard = 0
		self.save()

		if router_restored:
			return _(
				"Router Script restored from router.ts. Custom apps run it as plain JavaScript object. Remove import statements and TypeScript types if present."
			)

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
		# the router config lives in router.ts, so keep it out of the JSON
		write_document_file(self, folder=app_path, exclude_fields=["router_script"])
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

	def get_router_file_path(self) -> str:
		return os.path.join(self.get_folder_path(), "router.ts")

	def export_router_script_to_file(self):
		"""Move the router script into router.ts and clear the DB field. Called on enabling exports"""
		if not self.router_script:
			return
		if not os.path.exists(self.get_router_file_path()):
			with open(self.get_router_file_path(), "w") as f:
				f.write(f"export default {self.router_script.strip()}\n")
		self.db_set("router_script", None, update_modified=False)

	def restore_router_script_from_file(self) -> bool:
		"""Load router.ts back into the `router_script` field, so the config survives in DB-only
		mode (called before the export folder is deleted on un-export)."""
		if not os.path.exists(self.get_router_file_path()):
			return False
		source = frappe.read_file(self.get_router_file_path())
		self.router_script = re.sub(r"^\s*export\s+default\s+", "", source, count=1).strip()
		return True

	def remove_from_studio_apps_txt(self, name: str):
		if self.frappe_app != "studio":
			return

		path = frappe.get_app_path("studio", "studio_apps.txt")
		apps = frappe.get_file_items(path)
		if frappe.scrub(name) in apps:
			apps.remove(frappe.scrub(name))
			with open(path, "w") as f:
				f.write("\n".join(apps))

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

	def collect_files(self, script: str, script_dir: str, blocks) -> list[dict]:
		"""The custom Vue components `blocks` use and everything the script and those files import."""
		files = {}
		pending = [
			path for name in custom_vue_component_names(blocks) if (path := self.find_vue_component(name))
		]
		pending += self.resolve_imports(script, script_dir)

		while pending:
			path = pending.pop()
			if path in files:
				continue
			with open(self.resolve_file_path(path), encoding="utf-8") as f:
				files[path] = f.read()
			pending += self.resolve_imports(files[path], os.path.dirname(path))

		return [{"path": path, "content": files[path]} for path in sorted(files)]

	def write_files(self, files: list[dict]):
		"""Add copied files without replacing incompatible files already in the app."""
		targets = {}
		for file in files:
			if (
				not isinstance(file, dict)
				or not isinstance(file.get("path"), str)
				or not isinstance(file.get("content"), str)
			):
				frappe.throw(_("Invalid copied file."))
			path = file["path"]
			target = self.resolve_file_path(path)
			if not target.lower().endswith(EXTENSIONS):
				frappe.throw(_("Unsupported copied file: {0}").format(path))
			if target in targets and targets[target]["content"] != file["content"]:
				frappe.throw(_("The copy contains conflicting versions of {0}.").format(path))
			targets[target] = file

		for target, file in targets.items():
			if not os.path.exists(target):
				continue
			if os.path.isfile(target) and frappe.read_file(target) == file["content"]:
				continue
			frappe.throw(
				_("{0} already exists with different content. Rename it before pasting.").format(
					file["path"]
				),
				title=_("File conflict"),
			)

		for target, file in targets.items():
			if os.path.exists(target):
				continue
			os.makedirs(os.path.dirname(target), exist_ok=True)
			with open(target, "x", encoding="utf-8") as f:
				f.write(file["content"])

	def find_vue_component(self, name: str) -> str | None:
		matches = []
		for dirpath, _dirnames, filenames in os.walk(self.get_folder_path()):
			if f"{name}.vue" in filenames:
				matches.append(os.path.relpath(os.path.join(dirpath, f"{name}.vue"), self.get_folder_path()))
		if len(matches) > 1:
			frappe.throw(
				_("Custom component {0} is ambiguous: {1}").format(name, ", ".join(sorted(matches))),
				title=_("Duplicate component name"),
			)
		return matches[0] if matches else None

	def resolve_imports(self, source: str, from_dir: str) -> list[str]:
		paths = []
		for spec in IMPORT_RE.findall(source or ""):
			base = spec[len("@app/") :] if spec.startswith("@app/") else os.path.join(from_dir, spec)
			if path := self.resolve_module(os.path.normpath(base)):
				paths.append(path)
		return paths

	def resolve_module(self, base: str) -> str | None:
		"""Vite's lookup: the path itself, then with an extension, then an index file."""
		if os.path.isabs(base) or base == ".." or base.startswith(f"..{os.sep}"):
			return None
		candidates = [
			base,
			*(base + ext for ext in EXTENSIONS),
			*(os.path.join(base, f"index{ext}") for ext in (".ts", ".js")),
		]
		for candidate in candidates:
			if os.path.isfile(self.resolve_file_path(candidate)):
				return candidate
		return None

	def resolve_file_path(self, path: str) -> str:
		root = os.path.realpath(self.get_folder_path())
		target = os.path.realpath(os.path.join(root, path))
		if target == root or not target.startswith(root + os.sep):
			frappe.throw(_("Invalid file path: {0}").format(path), frappe.PermissionError)
		return target

	def get_folder_path(self, name: str | None = None, frappe_app: str | None = None):
		return frappe.get_app_source_path(frappe_app or self.frappe_app, "studio", name or self.name)


def move_folder(source: str, destination: str):
	if not os.path.exists(source) or os.path.exists(destination):
		return
	frappe.create_folder(os.path.dirname(destination))
	shutil.move(source, destination)


def custom_vue_component_names(blocks) -> set[str]:
	return {
		block["componentName"]
		for block in walk_blocks(blocks)
		if block.get("isCustomVueComponent") and block.get("componentName")
	}


def get_vite_dev_server_port():
	port_offset = frappe.conf.webserver_port - 8000
	return 8080 + port_offset


def get_vite_dev_server_host():
	return f"{frappe.local.site}:{get_vite_dev_server_port()}"
