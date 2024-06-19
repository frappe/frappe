import textwrap

PATCH_TEMPLATE = textwrap.dedent(
	'''
	import frappe

	def execute():
		"""{docstring}"""

		# Write your patch here.
		pass
'''
)

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
# required_apps = []

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {{
# 	"ToDo": "custom_app.overrides.CustomToDo"
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

gitignore_template = """
.DS_Store
*.swp
tags
node_modules

# https://github.com/github/gitignore/blob/main/Python.gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
#   For a library or package, you might want to ignore these files since the code is
#   intended to run in multiple environments; otherwise, check them in:
# .python-version

# pipenv
#   According to pypa/pipenv#598, it is recommended to include Pipfile.lock in version control.
#   However, in case of collaboration, if having platform-specific dependencies or dependencies
#   having no cross-platform support, pipenv may install dependencies that don't work, or not
#   install all needed dependencies.
#Pipfile.lock

# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#   https://python-poetry.org/docs/basic-usage/#commit-your-poetrylock-file-to-version-control
#poetry.lock

# pdm
#   Similar to Pipfile.lock, it is generally recommended to include pdm.lock in version control.
#pdm.lock
#   pdm stores project-wide configurations in .pdm.toml, but it is recommended to not include it
#   in version control.
#   https://pdm.fming.dev/latest/usage/project/#working-with-version-control
.pdm.toml
.pdm-python
.pdm-build/

# PEP 582; used by e.g. github.com/David-OConnor/pyflow and github.com/pdm-project/pdm
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

"""

github_workflow_template = """
name: CI

on:
  push:
    branches:
      - develop
  pull_request:

concurrency:
  group: develop-{app_name}-${{{{ github.event.number }}}}
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
        uses: actions/cache@v2
        with:
          path: ~/.cache/pip
          key: ${{{{ runner.os }}}}-pip-${{{{ hashFiles('**/*requirements.txt', '**/pyproject.toml', '**/setup.py', '**/setup.cfg') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-pip-
            ${{{{ runner.os }}}}-

      - name: Get yarn cache directory path
        id: yarn-cache-dir-path
        run: 'echo "dir=$(yarn cache dir)" >> $GITHUB_OUTPUT'

      - uses: actions/cache@v3
        id: yarn-cache
        with:
          path: ${{{{ steps.yarn-cache-dir-path.outputs.dir }}}}
          key: ${{{{ runner.os }}}}-yarn-${{{{ hashFiles('**/yarn.lock') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-yarn-

      - name: Install MariaDB Client
        run: sudo apt-get install mariadb-client-10.6

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
default_stages: [commit]
fail_fast: false


repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.3.0
    hooks:
      - id: trailing-whitespace
        files: "{app_name}.*"
        exclude: ".*json$|.*txt$|.*csv|.*md|.*svg"
      - id: check-yaml
      - id: check-merge-conflict
      - id: check-ast
      - id: check-json
      - id: check-toml
      - id: check-yaml
      - id: debug-statements

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        name: "Run ruff linter and apply fixes"
        args: ["--fix"]

      - id: ruff-format
        name: "Format Python code"

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

linter_workflow_template = """
name: Linters

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
        uses: actions/cache@v3
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

readme_ci_section = """
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

"""
