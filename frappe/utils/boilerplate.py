# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

import frappe, os, re
from frappe.utils import touch_file, encode, cstr

def make_boilerplate(dest, app_name):
	if not os.path.exists(dest):
		print("Destination directory does not exist")
		return

	# app_name should be in snake_case
	app_name = frappe.scrub(app_name)

	hooks = frappe._dict()
	hooks.app_name = app_name
	app_title = hooks.app_name.replace("_", " ").title()
	for key in ("App Title (default: {0})".format(app_title),
		"App Description", "App Publisher", "App Email",
		"App Icon (default 'octicon octicon-file-directory')",
		"App Color (default 'grey')",
		"App License (default 'MIT')"):
		hook_key = key.split(" (")[0].lower().replace(" ", "_")
		hook_val = None
		while not hook_val:
			hook_val = cstr(raw_input(key + ": "))

			if not hook_val:
				defaults = {
					"app_title": app_title,
					"app_icon": "octicon octicon-file-directory",
					"app_color": "grey",
					"app_license": "MIT"
				}
				if hook_key in defaults:
					hook_val = defaults[hook_key]

			if hook_key=="app_name" and hook_val.lower().replace(" ", "_") != hook_val:
				print("App Name must be all lowercase and without spaces")
				hook_val = ""
			elif hook_key=="app_title" and not re.match("^(?![\W])[^\d_\s][\w -]+$", hook_val, re.UNICODE):
				print("App Title should start with a letter and it can only consist of letters, numbers, spaces and underscores")
				hook_val = ""

		hooks[hook_key] = hook_val

	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, frappe.scrub(hooks.app_title)),
		with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "www"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates",
		"pages"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates",
		"includes"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "config"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public",
		"css"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public",
		"js"))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "__init__.py"), "w") as f:
		f.write(encode(init_template))

	with open(os.path.join(dest, hooks.app_name, "MANIFEST.in"), "w") as f:
		f.write(encode(manifest_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, ".gitignore"), "w") as f:
		f.write(encode(gitignore_template.format(app_name = hooks.app_name)))

	with open(os.path.join(dest, hooks.app_name, "setup.py"), "w") as f:
		f.write(encode(setup_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, "requirements.txt"), "w") as f:
		f.write("frappe")

	with open(os.path.join(dest, hooks.app_name, "README.md"), "w") as f:
		f.write(encode("## {0}\n\n{1}\n\n#### License\n\n{2}".format(hooks.app_title,
			hooks.app_description, hooks.app_license)))

	with open(os.path.join(dest, hooks.app_name, "license.txt"), "w") as f:
		f.write(encode("License: " + hooks.app_license))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "modules.txt"), "w") as f:
		f.write(encode(hooks.app_title))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "hooks.py"), "w") as f:
		f.write(encode(hooks_template.format(**hooks)))

	touch_file(os.path.join(dest, hooks.app_name, hooks.app_name, "patches.txt"))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "config", "desktop.py"), "w") as f:
		f.write(encode(desktop_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "config", "docs.py"), "w") as f:
		f.write(encode(docs_template.format(**hooks)))

	print("'{app}' created at {path}".format(app=app_name, path=os.path.join(dest, app_name)))


manifest_template = """include MANIFEST.in
include requirements.txt
include *.json
include *.md
include *.py
include *.txt
recursive-include {app_name} *.css
recursive-include {app_name} *.csv
recursive-include {app_name} *.html
recursive-include {app_name} *.ico
recursive-include {app_name} *.js
recursive-include {app_name} *.json
recursive-include {app_name} *.md
recursive-include {app_name} *.png
recursive-include {app_name} *.py
recursive-include {app_name} *.svg
recursive-include {app_name} *.txt
recursive-exclude {app_name} *.pyc"""

init_template = """# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'

"""

hooks_template = """# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "{app_name}"
app_title = "{app_title}"
app_publisher = "{app_publisher}"
app_description = "{app_description}"
app_icon = "{app_icon}"
app_color = "{app_color}"
app_email = "{app_email}"
app_license = "{app_license}"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/{app_name}/css/{app_name}.css"
# app_include_js = "/assets/{app_name}/js/{app_name}.js"

# include js, css files in header of web template
# web_include_css = "/assets/{app_name}/css/{app_name}.css"
# web_include_js = "/assets/{app_name}/js/{app_name}.js"

# include js in page
# page_js = {{"page" : "public/js/file.js"}}

# include js in doctype views
# doctype_js = {{"doctype" : "public/js/doctype.js"}}
# doctype_list_js = {{"doctype" : "public/js/doctype_list.js"}}
# doctype_tree_js = {{"doctype" : "public/js/doctype_tree.js"}}
# doctype_calendar_js = {{"doctype" : "public/js/doctype_calendar.js"}}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {{
#	"Role": "home_page"
# }}

# Website user home page (by function)
# get_website_user_home_page = "{app_name}.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "{app_name}.install.before_install"
# after_install = "{app_name}.install.after_install"

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
#	}}
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
# 	]
# 	"monthly": [
# 		"{app_name}.tasks.monthly"
# 	]
# }}

# Testing
# -------

# before_tests = "{app_name}.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {{
# 	"frappe.desk.doctype.event.event.get_events": "{app_name}.event.get_events"
# }}

"""

desktop_template = """# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{{
			"module_name": "{app_title}",
			"color": "{app_color}",
			"icon": "{app_icon}",
			"type": "module",
			"label": _("{app_title}")
		}}
	]
"""

setup_template = """# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
from pip.req import parse_requirements
import re, ast

# get version from __version__ variable in {app_name}/__init__.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('{app_name}/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

requirements = parse_requirements("requirements.txt", session="")

setup(
	name='{app_name}',
	version=version,
	description='{app_description}',
	author='{app_publisher}',
	author_email='{app_email}',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=[str(ir.req) for ir in requirements],
	dependency_links=[str(ir._link) for ir in requirements if ir._link]
)
"""

gitignore_template = """.DS_Store
*.pyc
*.egg-info
*.swp
tags
{app_name}/docs/current"""

docs_template = '''"""
Configuration for docs
"""

# source_link = "https://github.com/[org_name]/{app_name}"
# docs_base_url = "https://[org_name].github.io/{app_name}"
# headline = "App that does everything"
# sub_heading = "Yes, you got that right the first time, everything"

def get_context(context):
	context.brand_html = "{app_title}"
'''
