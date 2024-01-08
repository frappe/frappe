import json
import re
import tomllib

import requests

import frappe
from frappe.utils.caching import redis_cache


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw("You need to be logged in to access this page.", frappe.PermissionError)

	packages_by_app = {}
	for app in frappe.get_installed_apps():
		packages_by_app[app] = get_app_deps(app)

	context.packages_by_app = packages_by_app


@redis_cache(ttl=60 * 60 * 24 * 7)
def get_app_deps(app: str):
	dependencies = []

	app_info = get_pyproject_info(app)
	for requirement in app_info.get("dependencies", []):
		name, version = parse_pip_requirement(requirement)
		info = get_py_registry_info(name)
		info["name"] = name
		info["version"] = version
		dependencies.append(info)

	for name, version in get_js_deps(app).items():
		info = get_js_registry_info(name)
		info["name"] = name
		info["version"] = version
		dependencies.append(info)

	return dependencies


def get_js_deps(app: str):
	package_json = frappe.get_app_path(app, "..", "package.json")
	with open(package_json) as f:
		package = json.load(f)

	return package.get("dependencies", {})


def get_js_registry_info(package):
	registry_url = f"https://registry.npmjs.org/{package}"
	registry_info = requests.get(registry_url).json()
	return {
		"license": registry_info.get("license"),
		"author": registry_info.get("author", {}).get("name"),
		"homepage": registry_info.get("homepage"),
	}


def get_pyproject_info(app: str) -> list[str]:
	pyproject_toml = frappe.get_app_path(app, "..", "pyproject.toml")
	with open(pyproject_toml, "rb") as f:
		pyproject = tomllib.load(f)

	return pyproject.get("project", {})


def get_py_registry_info(package):
	registry_url = f"https://pypi.org/pypi/{package}/json"
	registry_info = requests.get(registry_url).json().get("info", {})
	return {
		"license": registry_info.get("license"),
		"author": registry_info.get("author"),
		"homepage": registry_info.get("home_page"),
	}


def parse_pip_requirement(requirement: str) -> tuple[str, str]:
	"""Parse pip requirement string to package name and version"""
	match = re.match(r"^([A-Za-z0-9_\-\[\]]+)(.*)$", requirement)

	return (match[1], match[2]) if match else (requirement, "")
