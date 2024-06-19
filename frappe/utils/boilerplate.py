# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextlib
import glob
import json
import os
import pathlib
import re
from pathlib import Path

import click
import git
import requests

import frappe
from frappe.utils.boilerplate_templates import (
	PATCH_TEMPLATE,
	github_workflow_template,
	gitignore_template,
	hooks_template,
	init_template,
	linter_workflow_template,
	patches_template,
	precommit_template,
	pyproject_template,
	readme_ci_section,
	readme_template,
)
from frappe.utils.change_log import get_app_branch

APP_TITLE_PATTERN = re.compile(r"^(?![\W])[^\d_\s][\w -]+$", flags=re.UNICODE)


def make_boilerplate(dest, app_name, no_git=False):
	if not os.path.exists(dest):
		print("Destination directory does not exist")
		return

	# app_name should be in snake_case
	app_name = frappe.scrub(app_name)
	hooks = _get_user_inputs(app_name)
	_create_app_boilerplate(dest, hooks, no_git=no_git)


def _get_user_inputs(app_name):
	"""Prompt user for various inputs related to new app and return config."""
	app_name = frappe.scrub(app_name)

	hooks = frappe._dict()
	hooks.app_name = app_name
	app_title = hooks.app_name.replace("_", " ").title()

	new_app_config = {
		"app_title": {
			"prompt": "App Title",
			"default": app_title,
			"validator": is_valid_title,
		},
		"app_description": {"prompt": "App Description"},
		"app_publisher": {"prompt": "App Publisher"},
		"app_email": {"prompt": "App Email", "validator": is_valid_email},
		"app_license": {
			"prompt": "App License",
			"default": "mit",
			"type": click.Choice(get_license_options()),
		},
		"create_github_workflow": {
			"prompt": "Create GitHub Workflow action for unittests",
			"default": False,
			"type": bool,
		},
		"branch_name": {"prompt": "Branch Name", "default": get_app_branch("frappe")},
	}

	for property, config in new_app_config.items():
		value = None
		input_type = config.get("type", str)

		while value is None:
			if input_type == bool:
				value = click.confirm(config["prompt"], default=config.get("default"))
			else:
				value = click.prompt(config["prompt"], default=config.get("default"), type=input_type)

			if validator_function := config.get("validator"):
				if not validator_function(value):
					value = None
		hooks[property] = value

	return hooks


def is_valid_email(email) -> bool:
	from email.headerregistry import Address

	try:
		Address(addr_spec=email)
	except Exception:
		print("App Email should be a valid email address.")
		return False
	return True


def is_valid_title(title) -> bool:
	if not APP_TITLE_PATTERN.match(title):
		print(
			"App Title should start with a letter and it can only consist of letters, numbers, spaces and underscores"
		)
		return False
	return True


def get_license_options() -> list[str]:
	url = "https://api.github.com/licenses"
	res = requests.get(url=url)
	if res.status_code == 200:
		res = res.json()
		ids = [r.get("spdx_id") for r in res]
		return [licencse.lower() for licencse in ids]

	return ["agpl-3.0", "gpl-3.0", "mit", "custom"]


def get_license_text(license_name: str) -> str:
	url = f"https://api.github.com/licenses/{license_name.lower()}"
	res = requests.get(url=url)
	if res.status_code == 200:
		res = res.json()
		return res.get("body")
	return license_name


def copy_from_frappe(rel_path: str, new_app_path: str):
	"""Copy files from frappe app to new app."""
	src = Path(frappe.get_app_path("frappe", "..")) / rel_path
	target = Path(new_app_path) / rel_path
	Path(target).write_text(Path(src).read_text())


def _create_app_boilerplate(dest, hooks, no_git=False):
	frappe.create_folder(
		os.path.join(dest, hooks.app_name, hooks.app_name, frappe.scrub(hooks.app_title)),
		with_init=True,
	)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "www"))
	frappe.create_folder(
		os.path.join(dest, hooks.app_name, hooks.app_name, "templates", "pages"), with_init=True
	)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates", "includes"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "config"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public", "css"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public", "js"))

	# add .gitkeep file so that public folder is committed to git
	# this is needed because if public doesn't exist, bench build doesn't symlink the apps assets
	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "public", ".gitkeep"), "w") as f:
		f.write("")

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "__init__.py"), "w") as f:
		f.write(frappe.as_unicode(init_template))

	with open(os.path.join(dest, hooks.app_name, "pyproject.toml"), "w") as f:
		f.write(frappe.as_unicode(pyproject_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, ".pre-commit-config.yaml"), "w") as f:
		f.write(frappe.as_unicode(precommit_template.format(**hooks)))

	license_body = get_license_text(license_name=hooks.app_license)
	with open(os.path.join(dest, hooks.app_name, "license.txt"), "w") as f:
		f.write(frappe.as_unicode(license_body))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "modules.txt"), "w") as f:
		f.write(frappe.as_unicode(hooks.app_title))

	# These values could contain quotes and can break string declarations
	# So escaping them before setting variables in setup.py and hooks.py
	for key in ("app_publisher", "app_description", "app_license"):
		hooks[key] = hooks[key].replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "hooks.py"), "w") as f:
		f.write(frappe.as_unicode(hooks_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "patches.txt"), "w") as f:
		f.write(frappe.as_unicode(patches_template.format(**hooks)))

	app_directory = os.path.join(dest, hooks.app_name)

	copy_from_frappe(".editorconfig", app_directory)
	copy_from_frappe(".eslintrc", app_directory)

	if hooks.create_github_workflow:
		_create_github_workflow_files(dest, hooks)
		hooks.readme_ci_section = readme_ci_section
	else:
		hooks.readme_ci_section = ""

	with open(os.path.join(dest, hooks.app_name, "README.md"), "w") as f:
		f.write(frappe.as_unicode(readme_template.format(**hooks)))

	if not no_git:
		with open(os.path.join(dest, hooks.app_name, ".gitignore"), "w") as f:
			f.write(frappe.as_unicode(gitignore_template.format(app_name=hooks.app_name)))

		# initialize git repository
		app_repo = git.Repo.init(app_directory, initial_branch=hooks.branch_name)
		app_repo.git.add(A=True)
		app_repo.index.commit("feat: Initialize App")

	print(f"'{hooks.app_name}' created at {app_directory}")


def _create_github_workflow_files(dest, hooks):
	workflows_path = pathlib.Path(dest) / hooks.app_name / ".github" / "workflows"
	workflows_path.mkdir(parents=True, exist_ok=True)

	ci_workflow = workflows_path / "ci.yml"
	with open(ci_workflow, "w") as f:
		f.write(github_workflow_template.format(**hooks))

	linter_workflow = workflows_path / "linter.yml"
	with open(linter_workflow, "w") as f:
		f.write(linter_workflow_template)


class PatchCreator:
	def __init__(self):
		self.all_apps = frappe.get_all_apps(sites_path=".", with_internal_apps=False)

		self.app = None
		self.app_dir = None
		self.patch_dir = None
		self.filename = None
		self.docstring = None
		self.patch_file = None

	def fetch_user_inputs(self):
		self._ask_app_name()
		self._ask_doctype_name()
		self._ask_patch_meta_info()

	def _ask_app_name(self):
		self.app = click.prompt("Select app for new patch", type=click.Choice(self.all_apps))
		self.app_dir = pathlib.Path(frappe.get_app_path(self.app))

	def _ask_doctype_name(self):
		def _doctype_name(filename):
			with contextlib.suppress(Exception):
				with open(filename) as f:
					return json.load(f).get("name")

		doctype_files = list(glob.glob(f"{self.app_dir}/**/doctype/**/*.json"))
		doctype_map = {_doctype_name(file): file for file in doctype_files}
		doctype_map.pop(None, None)

		doctype = click.prompt(
			"Provide DocType name on which this patch will apply",
			type=click.Choice(doctype_map.keys()),
			show_choices=False,
		)
		self.patch_dir = pathlib.Path(doctype_map[doctype]).parents[0] / "patches"

	def _ask_patch_meta_info(self):
		self.docstring = click.prompt("Describe what this patch does", type=str)
		default_filename = frappe.scrub(self.docstring) + ".py"

		def _valid_filename(name):
			if not name:
				return

			match name.partition("."):
				case filename, ".", "py" if filename.isidentifier():
					return True
				case _:
					click.echo(f"{name} is not a valid python file name")

		while not _valid_filename(self.filename):
			self.filename = click.prompt(
				"Provide filename for this patch", type=str, default=default_filename
			)

	def create_patch_file(self):
		self._create_parent_folder_if_not_exists()

		self.patch_file = self.patch_dir / self.filename

		if self.patch_file.exists():
			raise Exception(f"Patch {self.patch_file} already exists")

		*path, _filename = self.patch_file.relative_to(self.app_dir.parents[0]).parts
		dotted_path = ".".join([*path, self.patch_file.stem])

		patches_txt = self.app_dir / "patches.txt"
		existing_patches = patches_txt.read_text()

		if dotted_path in existing_patches:
			raise Exception(f"Patch {dotted_path} is already present in patches.txt")

		self.patch_file.write_text(PATCH_TEMPLATE.format(docstring=self.docstring))

		with open(patches_txt, "a+") as f:
			if not existing_patches.endswith("\n"):
				f.write("\n")  # ensure EOF
			f.write(dotted_path + "\n")
		click.echo(f"Created {self.patch_file} and updated patches.txt")

	def _create_parent_folder_if_not_exists(self):
		if not self.patch_dir.exists():
			click.confirm(
				f"Patch folder '{self.patch_dir}' doesn't exist, create it?",
				abort=True,
				default=True,
			)
			self.patch_dir.mkdir()

		init_py = self.patch_dir / "__init__.py"
		init_py.touch()
