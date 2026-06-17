# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import json
import os
import re

import click
import frappe
from frappe.build import get_node_env
from frappe.commands import popen
from frappe.utils import get_files_path

from studio.constants import DEFAULT_COMPONENTS, NON_VUE_COMPONENTS


class StudioAppBuilder:
	def __init__(self, studio_app: str, is_standard: bool, frappe_app: str | None = None):
		self.app_name = studio_app
		self.is_standard = is_standard
		self.frappe_app = frappe_app
		self.components = set(DEFAULT_COMPONENTS)
		self.studio_component_blocks = {}
		self.custom_vue_components: dict[str, str] = {}  # {ComponentName: absolute_path}
		self.page_scripts: list[dict] = []  # [{page_name, file_path}]

		if self.is_standard:
			"""Build a standard (exported) studio app.
			Output goes to: apps/{frappe_app}/{frappe_app}/public/app_builds/{app_name}/
			Served at: /assets/{frappe_app}/app_builds/{app_name}/
			"""
			self.out_dir = frappe.get_app_path(self.frappe_app, "public", "app_builds", self.app_name)
			self.base = f"/assets/{self.frappe_app}/app_builds/{self.app_name}/"
		else:
			"""Build a custom (DB) studio app for the current site.
			Output goes to: sites/{sitename}/public/files/app_builds/{app_name}/
			Served at: /files/app_builds/{app_name}/
			"""
			self.out_dir = os.path.abspath(get_files_path("app_builds", self.app_name))
			self.base = f"/files/app_builds/{self.app_name}/"

	def build(self):
		if self.is_standard:
			self.get_app_components_from_files()
			self.get_page_scripts_from_files()
		else:
			self.get_app_components()
		self._run_vite_build()

	def get_page_scripts_from_files(self):
		"""Collect the <page>.ts code files for the app's published pages, so the build bundles a
		`setup()` module per page (code mode)."""
		studio_folder = get_studio_folder(self.frappe_app)
		page_folder = os.path.join(studio_folder, self.app_name, "studio_page")
		if not page_folder or not os.path.isdir(page_folder):
			return

		scripts = []
		# each page is a folder holding <stem>.json + <stem>.ts
		for entry in sorted(os.listdir(page_folder)):
			page_dir = os.path.join(page_folder, entry)
			if not os.path.isdir(page_dir):
				continue
			ts_path = os.path.join(page_dir, f"{entry}.ts")
			json_path = os.path.join(page_dir, f"{entry}.json")
			if not (os.path.exists(ts_path) and os.path.exists(json_path)):
				continue
			try:
				with open(json_path) as f:
					page_name = json.load(f).get("page_name")
			except (OSError, json.JSONDecodeError):
				continue
			if page_name:
				scripts.append({"page_name": page_name, "file_path": ts_path})

		self.page_scripts = scripts
		return scripts

	def _run_vite_build(self) -> None:
		"""Execute the yarn build-studio-app command with the given parameters."""
		if not self.components:
			click.echo(f"No components found for {self.app_name}, skipping build")
			return

		os.makedirs(self.out_dir, exist_ok=True)

		components_str = ",".join(sorted(self.components))
		command = (
			f"yarn build-studio-app"
			f" --app {self.app_name}"
			f" --components {components_str}"
			f" --out-dir {self.out_dir}"
			f" --base {self.base}"
		)

		if self.custom_vue_components:
			custom_json = json.dumps(self.custom_vue_components)
			command += f" --custom-components '{custom_json}'"

		if self.page_scripts:
			page_scripts_json = json.dumps(self.page_scripts)
			command += f" --page-scripts '{page_scripts_json}'"

		studio_app_path = frappe.get_app_source_path("studio")
		popen(command, cwd=studio_app_path, env=get_node_env(), raise_err=True)

	def get_app_components(self) -> set[str]:
		pages = frappe.get_all(
			"Studio Page",
			filters={"studio_app": self.app_name, "published": 1, "blocks": ("is", "set")},
			pluck="blocks",
		)
		if not pages:
			return set()

		for blocks in pages:
			if not blocks:
				continue
			if isinstance(blocks, str):
				self._add_h_function_components(blocks)
				blocks = frappe.parse_json(blocks)
			root_block = blocks[0]
			self._add_block_components(root_block)

	def get_app_components_from_files(self):
		"""Extract component names from exported JSON files on disk instead of DB records,
		used during `bench build` when there's no DB access.
		"""
		studio_folder = get_studio_folder(self.frappe_app)
		app_folder = os.path.join(studio_folder, self.app_name)
		page_folder = os.path.join(app_folder, "studio_page")
		if not os.path.exists(page_folder):
			return self.components

		self._load_studio_components_from_files(app_folder)

		# each page is a folder holding <stem>.json + <stem>.ts
		for entry in os.listdir(page_folder):
			page_dir = os.path.join(page_folder, entry)
			if not os.path.isdir(page_dir):
				continue
			page_path = os.path.join(page_dir, f"{entry}.json")
			if not os.path.exists(page_path):
				continue
			try:
				with open(page_path) as f:
					page_data = json.load(f)
			except (json.JSONDecodeError, OSError) as e:
				click.secho(f"Warning: Could not read {page_path}: {e}", fg="yellow")
				continue

			blocks = page_data.get("blocks")
			if not blocks:
				continue

			if isinstance(blocks, str):
				self._add_h_function_components(blocks)
				blocks = json.loads(blocks)

			if isinstance(blocks, list) and blocks:
				self._add_block_components(blocks[0])

	def _add_h_function_components(self, text: str) -> None:
		"""Extract component names from h(ComponentName...) function calls"""
		pattern = r"\bh\(\s*([A-Z][a-zA-Z0-9_]*)"

		matches = re.findall(pattern, text)
		for match in matches:
			self.components.add(match)

	def _add_block_components(self, block: dict) -> None:
		if block.get("isStudioComponent"):
			self._add_studio_components(block)
		elif block.get("isCustomVueComponent"):
			self._add_custom_vue_component(block.get("componentName"))
		elif block.get("componentName") not in NON_VUE_COMPONENTS:
			self.components.add(block.get("componentName"))
		for child in block.get("children", []):
			self._add_block_components(child)

		if slots := block.get("componentSlots"):
			for slot in slots.values():
				if isinstance(slot.get("slotContent"), str):
					continue
				for slot_child in slot.get("slotContent"):
					self._add_block_components(slot_child)

	def _add_studio_components(self, block: dict):
		if self.is_standard:
			comp_name = block.get("componentName")
			if comp_name and comp_name in self.studio_component_blocks:
				self._add_block_components(self.studio_component_blocks[comp_name])
		else:
			component_block = frappe.db.get_value("Studio Component", block.get("componentName"), "block")
			if isinstance(component_block, str):
				component_block = frappe.parse_json(component_block)
			self._add_block_components(component_block)

	def _load_studio_components_from_files(self, app_folder: str):
		"""Load all studio component definitions from disk for recursive component resolution."""
		self.studio_component_blocks = {}
		components_folder = os.path.join(app_folder, "studio_components")

		if not os.path.exists(components_folder):
			return self.studio_component_blocks
		for file in os.listdir(components_folder):
			if not file.endswith(".json"):
				continue

			component_file_path = os.path.join(components_folder, file)
			try:
				with open(component_file_path) as f:
					component = json.load(f)

				component_name = component.get("name")
				block = component.get("block")

				if component_name and block:
					if isinstance(block, str):
						block = json.loads(block)
					self.studio_component_blocks[component_name] = block
			except (json.JSONDecodeError, OSError):
				continue

	def _add_custom_vue_component(self, componentName: str):
		if not componentName or not self.frappe_app:
			return

		studio_folder = get_studio_folder(self.frappe_app)
		if not studio_folder:
			return

		app_dir = os.path.join(studio_folder, self.app_name)
		for dirpath, _dirnames, filenames in os.walk(app_dir):
			if f"{componentName}.vue" in filenames:
				self.custom_vue_components[componentName] = os.path.join(dirpath, f"{componentName}.vue")
				break


def build_standard_apps(app: str | None = None) -> None:
	"""Scan all apps on the bench for studio/ folders and build each exported app.

	This function works without DB access — it reads component data from
	exported JSON files on disk.

	Args:
	        app: Only build studio apps exported to this specific frappe app
	"""
	apps = [app] if app else frappe.get_all_apps()

	for frappe_app in apps:
		studio_folder = get_studio_folder(frappe_app)
		if not os.path.exists(studio_folder):
			continue

		if frappe_app == "studio":
			apps_list_file = frappe.get_app_path("studio", "studio_apps.txt")
			if os.path.exists(apps_list_file):
				studio_apps = frappe.get_file_items(apps_list_file)
			else:
				continue
		else:
			studio_apps = [
				d for d in os.listdir(studio_folder) if os.path.isdir(os.path.join(studio_folder, d))
			]

		for studio_app in studio_apps:
			click.echo(f"\nBuilding Studio App: {studio_app} (from {frappe_app})")

			try:
				StudioAppBuilder(studio_app, is_standard=True, frappe_app=frappe_app).build()
				click.echo(click.style("✔", fg="green") + f" Built {studio_app}")
			except Exception:
				click.echo(click.style("✖", fg="red") + f" Build failed for {studio_app}")


def build_custom_apps() -> None:
	"""Build all published custom (DB) studio apps for the current site.
	Requires site context (DB access).
	"""
	custom_apps = get_published_custom_apps()

	for app_name in custom_apps:
		click.echo(f"\nBuilding Custom Studio App: {app_name}")
		try:
			StudioAppBuilder(app_name, is_standard=False).build()
		except Exception as e:
			click.secho(f"Failed to build {app_name}: {e}", fg="red")


def get_published_custom_apps() -> list[str]:
	StudioApp = frappe.qb.DocType("Studio App")
	StudioPage = frappe.qb.DocType("Studio Page")
	custom_apps = (
		(
			frappe.qb.from_(StudioApp)
			.inner_join(StudioPage)
			.on(StudioPage.studio_app == StudioApp.name)
			.select(StudioApp.name)
			.where(StudioApp.is_standard == 0)
			.where(StudioPage.published == 1)
		)
		.distinct()
		.run(pluck=True)
	)

	return custom_apps


def get_studio_folder(frappe_app: str) -> str | None:
	return frappe.get_app_source_path(frappe_app, "studio")


def after_build() -> None:
	"""Hook called after `bench build`. Builds all standard studio apps"""
	click.secho("\nBuilding Studio Apps...", fg="cyan")
	build_standard_apps()
