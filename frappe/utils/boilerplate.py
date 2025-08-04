# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextlib
import glob
import json
import os
import pathlib
import re
import textwrap
from pathlib import Path

import click
import git
import requests

import frappe
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
			if input_type is bool:
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
	try:
		res = requests.get(url=url)
	except requests.exceptions.RequestException:
		return ["agpl-3.0", "gpl-3.0", "mit", "custom"]

	if res.status_code == 200:
		res = res.json()
		ids = [r.get("spdx_id") for r in res]
		return [licencse.lower() for licencse in ids]

	return ["agpl-3.0", "gpl-3.0", "mit", "custom"]


def get_license_text(license_name: str) -> str:
	url = f"https://api.github.com/licenses/{license_name.lower()}"
	try:
		res = requests.get(url=url)
	except requests.exceptions.RequestException:
		return "No license text found"
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

	with open(
		os.path.join(dest, hooks.app_name, hooks.app_name, frappe.scrub(hooks.app_title), ".frappe"), "w"
	) as f:
		f.write("")

	from frappe.deprecation_dumpster import boilerplate_modules_txt

	boilerplate_modules_txt(dest, hooks.app_name, hooks.app_title)

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


PATCH_TEMPLATE = textwrap.dedent(
	'''
	import frappe

	def execute():
		"""{docstring}"""

		# Write your patch here.
		pass
'''
)


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


init_template = """__version__ = "0.0.1"
"""

pyproject_template = """[project]
name = "{app_name}"
authors = [
    {{ name = "{app_publisher}", email = "{app_email}"}}
]
description = "{app_description}"
requires-python = ">=3.10"
readme = "README.md"
dynamic = ["version"]
dependencies = [
    # "frappe~=15.0.0" # Installed and managed by bench.
]

[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"

# These dependencies are only installed when developer mode is enabled
[tool.bench.dev-dependencies]
# package_name = "~=1.1.0"

[tool.ruff]
line-length = 110
target-version = "py310"

[tool.ruff.lint]
select = [
    "F",
    "E",
    "W",
    "I",
    "UP",
    "B",
    "RUF",
]
ignore = [
    "B017", # assertRaises(Exception) - should be more specific
    "B018", # useless expression, not assigned to anything
    "B023", # function doesn't bind loop variable - will have last iteration's value
    "B904", # raise inside except without from
    "E101", # indentation contains mixed spaces and tabs
    "E402", # module level import not at top of file
    "E501", # line too long
    "E741", # ambiguous variable name
    "F401", # "unused" imports
    "F403", # can't detect undefined names from * import
    "F405", # can't detect undefined names from * import
    "F722", # syntax error in forward type annotation
    "W191", # indentation contains tabs
    "UP030", # Use implicit references for positional format fields (translations)
    "UP031", # Use format specifiers instead of percent format
    "UP032", # Use f-string instead of `format` call (translations)
]
typing-modules = ["frappe.types.DF"]

[tool.ruff.format]
quote-style = "double"
indent-style = "tab"
docstring-code-format = true
"""

hooks_template = """app_name = "{app_name}"
app_title = "{app_title}"
app_publisher = "{app_publisher}"
app_description = "{app_description}"
app_email = "{app_email}"
app_license = "{app_license}"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{{
# 		"name": "{app_name}",
# 		"logo": "/assets/{app_name}/logo.png",
# 		"title": "{app_title}",
# 		"route": "/{app_name}",
# 		"has_permission": "{app_name}.api.permission.has_app_permission"
# 	}}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/{app_name}/css/{app_name}.css"
# app_include_js = "/assets/{app_name}/js/{app_name}.js"

# include js, css files in header of web template
# web_include_css = "/assets/{app_name}/css/{app_name}.css"
# web_include_js = "/assets/{app_name}/js/{app_name}.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "{app_name}/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {{"doctype": "public/js/doctype.js"}}
# webform_include_css = {{"doctype": "public/css/doctype.css"}}

# include js in page
# page_js = {{"page" : "public/js/file.js"}}

# include js in doctype views
# doctype_js = {{"doctype" : "public/js/doctype.js"}}
# doctype_list_js = {{"doctype" : "public/js/doctype_list.js"}}
# doctype_tree_js = {{"doctype" : "public/js/doctype_tree.js"}}
# doctype_calendar_js = {{"doctype" : "public/js/doctype_calendar.js"}}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "{app_name}/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {{
# 	"Role": "home_page"
# }}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {{
# 	"methods": "{app_name}.utils.jinja_methods",
# 	"filters": "{app_name}.utils.jinja_filters"
# }}

# Installation
# ------------

# before_install = "{app_name}.install.before_install"
# after_install = "{app_name}.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "{app_name}.uninstall.before_uninstall"
# after_uninstall = "{app_name}.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "{app_name}.utils.before_app_install"
# after_app_install = "{app_name}.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "{app_name}.utils.before_app_uninstall"
# after_app_uninstall = "{app_name}.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "{app_name}.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {{
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }}
#
# has_permission = {{
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {{
# 	"*": {{
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}}
# }}

# Scheduled Tasks
# ---------------

# scheduler_events = {{
# 	"all": [
# 		"{app_name}.tasks.all"
# 	],
# 	"daily": [
# 		"{app_name}.tasks.daily"
# 	],
# 	"hourly": [
# 		"{app_name}.tasks.hourly"
# 	],
# 	"weekly": [
# 		"{app_name}.tasks.weekly"
# 	],
# 	"monthly": [
# 		"{app_name}.tasks.monthly"
# 	],
# }}

# Testing
# -------

# before_tests = "{app_name}.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {{
# 	"frappe.desk.doctype.event.event.get_events": "{app_name}.event.get_events"
# }}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {{
# 	"Task": "{app_name}.task.get_dashboard_data"
# }}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["{app_name}.utils.before_request"]
# after_request = ["{app_name}.utils.after_request"]

# Job Events
# ----------
# before_job = ["{app_name}.utils.before_job"]
# after_job = ["{app_name}.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{{
# 		"doctype": "{{doctype_1}}",
# 		"filter_by": "{{filter_by}}",
# 		"redact_fields": ["{{field_1}}", "{{field_2}}"],
# 		"partial": 1,
# 	}},
# 	{{
# 		"doctype": "{{doctype_2}}",
# 		"filter_by": "{{filter_by}}",
# 		"partial": 1,
# 	}},
# 	{{
# 		"doctype": "{{doctype_3}}",
# 		"strict": False,
# 	}},
# 	{{
# 		"doctype": "{{doctype_4}}"
# 	}}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"{app_name}.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {{
# 	"Logging DocType Name": 30  # days to retain logs
# }}

"""

gitignore_template = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class
*.pyc
*.py~

# Distribution / packaging
.Python
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
tags
MANIFEST

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Dependency directories
node_modules/
jspm_packages/

# IDEs and editors
.vscode/
.vs/
.idea/
.kdev4/
*.kdev4
*.DS_Store
*.swp
*.comp.js
.wnf-lang-status
*debug.log

# Helix Editor
.helix/

# Aider AI Chat
.aider*
"""

github_workflow_template = """name: CI

on:
  push:
    branches:
      - {branch_name}
  pull_request:

concurrency:
  group: {branch_name}-{app_name}-${{{{ github.event.number }}}}
  cancel-in-progress: true

jobs:
  tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
    name: Server

    services:
      redis-cache:
        image: redis:alpine
        ports:
          - 13000:6379
      redis-queue:
        image: redis:alpine
        ports:
          - 11000:6379
      mariadb:
        image: mariadb:10.6
        env:
          MYSQL_ROOT_PASSWORD: root
        ports:
          - 3306:3306
        options: --health-cmd="mariadb-admin ping" --health-interval=5s --health-timeout=2s --health-retries=3

    steps:
      - name: Clone
        uses: actions/checkout@v3

      - name: Find tests
        run: |
          echo "Finding tests"
          grep -rn "def test" > /dev/null

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18
          check-latest: true

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{{{ runner.os }}}}-pip-${{{{ hashFiles('**/*requirements.txt', '**/pyproject.toml', '**/setup.py', '**/setup.cfg') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-pip-
            ${{{{ runner.os }}}}-

      - name: Get yarn cache directory path
        id: yarn-cache-dir-path
        run: 'echo "dir=$(yarn cache dir)" >> $GITHUB_OUTPUT'

      - uses: actions/cache@v4
        id: yarn-cache
        with:
          path: ${{{{ steps.yarn-cache-dir-path.outputs.dir }}}}
          key: ${{{{ runner.os }}}}-yarn-${{{{ hashFiles('**/yarn.lock') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-yarn-

      - name: Install MariaDB Client
        run: |
          sudo apt update
          sudo apt-get install mariadb-client

      - name: Setup
        run: |
          pip install frappe-bench
          bench init --skip-redis-config-generation --skip-assets --python "$(which python)" ~/frappe-bench
          mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
          mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"

      - name: Install
        working-directory: /home/runner/frappe-bench
        run: |
          bench get-app {app_name} $GITHUB_WORKSPACE
          bench setup requirements --dev
          bench new-site --db-root-password root --admin-password admin test_site
          bench --site test_site install-app {app_name}
          bench build
        env:
          CI: 'Yes'

      - name: Run Tests
        working-directory: /home/runner/frappe-bench
        run: |
          bench --site test_site set-config allow_tests true
          bench --site test_site run-tests --app {app_name}
        env:
          TYPE: server
"""

patches_template = """[pre_model_sync]
# Patches added in this section will be executed before doctypes are migrated
# Read docs to understand patches: https://frappeframework.com/docs/v14/user/en/database-migrations

[post_model_sync]
# Patches added in this section will be executed after doctypes are migrated"""


precommit_template = """exclude: 'node_modules|.git'
default_stages: [pre-commit]
fail_fast: false


repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        files: "{app_name}.*"
        exclude: ".*json$|.*txt$|.*csv|.*md|.*svg"
      - id: check-merge-conflict
      - id: check-ast
      - id: check-json
      - id: check-toml
      - id: check-yaml
      - id: debug-statements

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.1
    hooks:
      - id: ruff
        name: "Run ruff import sorter"
        args: ["--select=I", "--fix"]

      - id: ruff
        name: "Run ruff linter"

      - id: ruff-format
        name: "Run ruff formatter"

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v2.7.1
    hooks:
      - id: prettier
        types_or: [javascript, vue, scss]
        # Ignore any files that might contain jinja / bundles
        exclude: |
            (?x)^(
                {app_name}/public/dist/.*|
                .*node_modules.*|
                .*boilerplate.*|
                {app_name}/templates/includes/.*|
                {app_name}/public/js/lib/.*
            )$


  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.44.0
    hooks:
      - id: eslint
        types_or: [javascript]
        args: ['--quiet']
        # Ignore any files that might contain jinja / bundles
        exclude: |
            (?x)^(
                {app_name}/public/dist/.*|
                cypress/.*|
                .*node_modules.*|
                .*boilerplate.*|
                {app_name}/templates/includes/.*|
                {app_name}/public/js/lib/.*
            )$

ci:
    autoupdate_schedule: weekly
    skip: []
    submodules: false
"""

linter_workflow_template = """name: Linters

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  linter:
    name: 'Frappe Linter'
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: pip
      - uses: pre-commit/action@v3.0.0

      - name: Download Semgrep rules
        run: git clone --depth 1 https://github.com/frappe/semgrep-rules.git frappe-semgrep-rules

      - name: Run Semgrep rules
        run: |
          pip install semgrep
          semgrep ci --config ./frappe-semgrep-rules/rules --config r/python.lang.correctness

  deps-vulnerable-check:
    name: 'Vulnerable Dependency Check'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - uses: actions/checkout@v4

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/*requirements.txt', '**/pyproject.toml', '**/setup.py') }}
          restore-keys: |
            ${{ runner.os }}-pip-
            ${{ runner.os }}-

      - name: Install and run pip-audit
        run: |
          pip install pip-audit
          cd ${GITHUB_WORKSPACE}
          pip-audit --desc on .
"""

readme_template = """### {app_title}

{app_description}

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch {branch_name}
bench install-app {app_name}
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/{app_name}
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
{readme_ci_section}
### License

{app_license}
"""

readme_ci_section = """### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

"""
