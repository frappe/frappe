# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

"""
Studio app build orchestration.

This module provides functions to build studio apps for two scenarios:
1. Standard (exported) apps — built from disk JSON files, output to the
   host app's public/ folder
2. Custom (DB) apps — built from database records, output to the site's
   public/files/ folder
"""

import json
import os
import re

import click
import frappe
from frappe.build import get_node_env
from frappe.commands import popen
from frappe.utils import get_files_path


def build_standard_app(app_name: str, frappe_app: str, components: set[str]) -> None:
	"""Build a standard (exported) studio app.

	Output goes to: apps/{frappe_app}/{frappe_app}/public/app_builds/{app_name}/
	Served at:      /assets/{frappe_app}/app_builds/{app_name}/
	"""
	out_dir = frappe.get_app_path(frappe_app, "public", "app_builds", app_name)
	base = f"/assets/{frappe_app}/app_builds/{app_name}/"
	_run_vite_build(app_name, components, out_dir, base)


def build_custom_app(app_name: str, components: set[str]) -> None:
	"""Build a custom (DB) studio app for the current site.

	Output goes to: sites/{site}/public/files/app_builds/{app_name}/
	Served at:      /files/app_builds/{app_name}/
	"""
	out_dir = os.path.abspath(get_files_path("app_builds", app_name))
	base = f"/files/app_builds/{app_name}/"
	_run_vite_build(app_name, components, out_dir, base)


def _run_vite_build(app_name: str, components: set[str], out_dir: str, base: str) -> None:
	"""Execute the yarn build-studio-app command with the given parameters."""
	if not components:
		click.echo(f"  No components found for {app_name}, skipping build")
		return

	os.makedirs(out_dir, exist_ok=True)

	components_str = ",".join(sorted(components))
	command = (
		f"yarn build-studio-app"
		f" --app {app_name}"
		f" --components {components_str}"
		f" --out-dir {out_dir}"
		f" --base {base}"
	)

	studio_app_path = frappe.get_app_source_path("studio")
	popen(command, cwd=studio_app_path, env=get_node_env(), raise_err=True)


def build_standard_apps(app: str | None = None) -> None:
	"""Scan all apps on the bench for studio/ folders and build each exported app.

	This function works without DB access — it reads component data from
	exported JSON files on disk.

	Args:
	        app: Only build studio apps exported to this specific frappe app
	"""
	apps = [app] if app else frappe.get_all_apps()

	for app in apps:
		studio_folder = frappe.get_app_source_path(app, "studio")
		if not os.path.exists(studio_folder):
			continue

		if app == "studio":
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
			app_folder = os.path.join(studio_folder, studio_app)
			if not os.path.isdir(app_folder):
				continue

			click.echo(f"\nBuilding Studio App: {studio_app} (from {app})")

			try:
				components = get_components_from_disk(app_folder)
				if components:
					build_standard_app(studio_app, app, components)
				else:
					click.echo("  No components found, skipping")
			except Exception as e:
				click.secho(f"  Failed to build {studio_app}: {e}", fg="red")


def build_custom_apps() -> None:
	"""Build all published custom (DB) studio apps for the current site.

	Requires site context (DB access).
	"""
	from studio.api import get_app_components

	custom_apps = frappe.get_all(
		"Studio App",
		filters={"is_standard": 0, "published": 1},
		pluck="name",
	)

	for app_name in custom_apps:
		click.echo(f"\nBuilding custom Studio App: {app_name}")
		try:
			components = get_app_components(app_name)
			if components:
				build_custom_app(app_name, components)
			else:
				click.echo("  No components found, skipping")
		except Exception as e:
			click.secho(f"  Failed to build {app_name}: {e}", fg="red")


def get_components_from_disk(app_folder: str) -> set[str]:
	"""Extract component names from exported JSON files on disk.

	This is the disk-based equivalent of `studio.api.get_app_components()`,
	used during `bench build` when there's no DB access.
	"""
	from studio.constants import DEFAULT_COMPONENTS, NON_VUE_COMPONENTS

	components = set(DEFAULT_COMPONENTS)

	# Read all page JSON files
	page_folder = os.path.join(app_folder, "studio_page")
	if not os.path.exists(page_folder):
		return components

	# Load studio components from disk for recursive resolution
	component_blocks = _load_studio_components_from_disk(app_folder)

	for page_file in os.listdir(page_folder):
		if not page_file.endswith(".json"):
			continue

		page_path = os.path.join(page_folder, page_file)
		try:
			with open(page_path) as f:
				page_data = json.load(f)
		except (json.JSONDecodeError, OSError) as e:
			click.secho(f"  Warning: Could not read {page_file}: {e}", fg="yellow")
			continue

		blocks = page_data.get("blocks")
		if not blocks:
			continue

		if isinstance(blocks, str):
			_add_h_function_components(blocks, components)
			blocks = json.loads(blocks)

		if isinstance(blocks, list) and blocks:
			_add_block_components(blocks[0], components, component_blocks, NON_VUE_COMPONENTS)

	return components


def _load_studio_components_from_disk(app_folder: str) -> dict[str, dict]:
	"""Load all studio component definitions from disk for recursive component resolution."""
	component_blocks = {}
	components_folder = os.path.join(app_folder, "studio_components")

	if not os.path.exists(components_folder):
		return component_blocks

	for comp_file in os.listdir(components_folder):
		if not comp_file.endswith(".json"):
			continue

		comp_path = os.path.join(components_folder, comp_file)
		try:
			with open(comp_path) as f:
				comp_data = json.load(f)

			comp_name = comp_data.get("name")
			block = comp_data.get("block")

			if comp_name and block:
				if isinstance(block, str):
					block = json.loads(block)
				component_blocks[comp_name] = block
		except (json.JSONDecodeError, OSError):
			continue

	return component_blocks


def _add_h_function_components(text: str, components: set[str]) -> None:
	"""Extract component names from h(ComponentName...) function calls."""
	pattern = r"\bh\(\s*([A-Z][a-zA-Z0-9_]*)"
	for match in re.findall(pattern, text):
		components.add(match)


def _add_block_components(
	block: dict,
	components: set[str],
	studio_component_blocks: dict[str, dict],
	non_vue_components: list[str],
) -> None:
	"""Recursively extract component names from a block tree."""

	if block.get("isStudioComponent"):
		comp_name = block.get("componentName")
		if comp_name and comp_name in studio_component_blocks:
			_add_block_components(
				studio_component_blocks[comp_name],
				components,
				studio_component_blocks,
				non_vue_components,
			)
	elif block.get("componentName") not in non_vue_components:
		components.add(block.get("componentName"))

	for child in block.get("children", []):
		_add_block_components(child, components, studio_component_blocks, non_vue_components)

	if slots := block.get("componentSlots"):
		for slot in slots.values():
			if isinstance(slot.get("slotContent"), str):
				continue
			for slot_child in slot.get("slotContent", []):
				_add_block_components(slot_child, components, studio_component_blocks, non_vue_components)


def after_build() -> None:
	"""Hook called after `bench build`. Builds all standard studio apps"""
	click.echo(click.style("\nBuilding Studio Apps...", fg="cyan"))
	build_standard_apps()
	click.echo(click.style("Studio Apps built", fg="green"))
