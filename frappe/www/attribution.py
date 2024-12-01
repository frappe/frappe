import json
import re
from pathlib import Path

import tomli

import frappe
from frappe import _
from frappe.permissions import is_system_user


def get_context(context):
	if not is_system_user():
		frappe.throw(_("You need to be a system user to access this page."), frappe.PermissionError)

	apps = []
	for app in frappe.get_installed_apps():
		app_info = get_app_info(app)
		if any([app_info.get("authors"), app_info.get("dependencies"), app_info.get("description")]):
			apps.append(app_info)

	context.apps = apps


def get_app_info(app: str):
	app_info = get_pyproject_info(app)
	result = {
		"name": app,
		"description": app_info.get("description", ""),
		"authors": ", ".join([a.get("name", "") for a in app_info.get("authors", [])]),
		"dependencies": [],
	}

	for requirement in app_info.get("dependencies", []):
		name = parse_pip_requirement(requirement)
		result["dependencies"].append({"name": name, "type": "Python"})

	result["dependencies"].extend(get_js_deps(app))

	return result


def get_js_deps(app: str) -> list[dict]:
	package_json = Path(frappe.get_app_path(app, "..", "package.json"))
	if not package_json.exists():
		return {}

	with open(package_json) as f:
		package = json.load(f)

	packages = package.get("dependencies", {}).keys()
	return [{"name": name, "type": "JavaScript"} for name in packages]


def get_pyproject_info(app: str) -> dict:
	pyproject_toml = Path(frappe.get_app_path(app, "..", "pyproject.toml"))
	if not pyproject_toml.exists():
		return {}

	with open(pyproject_toml, "rb") as f:
		pyproject = tomli.load(f)

	return pyproject.get("project", {})


def parse_pip_requirement(requirement: str) -> str:
	"""Parse pip requirement string to package name and version"""
	match = re.match(r"^([A-Za-z0-9_\-\[\]]+)(.*)$", requirement)

	return match[1] if match else requirement
