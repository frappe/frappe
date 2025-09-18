import contextlib
import importlib.metadata
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
		metadata = get_python_package_metadata(name)
		result["dependencies"].append(
			{"name": name, "type": "Python", "license": metadata["license"], "author": metadata["author"]}
		)

	result["dependencies"].extend(get_js_deps(app))

	return result


def get_python_package_metadata(package_name: str) -> dict:
	"""Get metadata for a Python package using importlib.metadata"""
	try:
		metadata = importlib.metadata.metadata(package_name)
		return {
			"license": (
				metadata.get("License-Expression")
				or parse_classifiers(metadata.get_all("Classifier", []))
				or metadata.get("License")  # May contain a full license text, less preferred
				or "Unknown"
			),
			"author": (
				metadata.get("Author")
				or metadata.get("Maintainer")
				or metadata.get("Author-email")
				or metadata.get("Maintainer-email")
				or "Unknown"
			),
		}
	except importlib.metadata.PackageNotFoundError:
		return {"license": "Unknown", "author": "Unknown"}


def parse_classifiers(classifiers: list[str]) -> str | None:
	"""Parse classifiers to get the license"""
	for classifier in classifiers:
		if classifier.startswith("License ::"):
			return classifier.split("::")[-1].strip()

	return None


def get_js_deps(app: str) -> list[dict]:
	package_json = Path(frappe.get_app_path(app, "..", "package.json"))
	if not package_json.exists():
		return []

	with open(package_json) as f:
		package = json.load(f)

	packages = package.get("dependencies", {}).keys()
	result = []

	# Get the node_modules directory
	node_modules_path = Path(frappe.get_app_path(app, "..", "node_modules"))

	for name in packages:
		# Initialize with basic info
		package_info = {"name": name, "type": "JavaScript", "license": "Unknown", "author": "Unknown"}

		# Try to find package.json in node_modules
		package_json_path = node_modules_path / name / "package.json"
		if package_json_path.exists():
			pkg_data = None
			with contextlib.suppress(json.JSONDecodeError):
				pkg_data = json.loads(package_json_path.read_text())
			if not pkg_data:
				continue

			# Extract license info
			license_info = pkg_data.get("license")
			if isinstance(license_info, dict):
				license_info = license_info.get("type")

			if license_info:
				package_info["license"] = license_info

			# Extract author info
			author = pkg_data.get("author")
			if isinstance(author, dict):
				author = author.get("name")
			if not author:
				maintainers = pkg_data.get("maintainers", [])
				if maintainers:
					author = ", ".join([m for m in maintainers if m])
			if author:
				package_info["author"] = author

		result.append(package_info)

	return result


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
