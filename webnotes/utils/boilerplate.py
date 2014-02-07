# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes, os
from webnotes.utils import touch_file

def make_boilerplate():
	if not os.path.exists("sites"):
		print "Run from bench! (sites folder must exist)"
		return
	
	hooks = webnotes._dict()
	for key in ("App Name", "App Title", "App Description", "App Publisher", 
		"App Icon", "App Color", "App Email", "App URL", "App License"):
		hook_key = key.lower().replace(" ", "_")
		hook_val = None
		while not hook_val:
			hook_val = raw_input(key + ": ")
			if hook_key=="app_name" and hook_val.lower().replace(" ", "_") != hook_val:
				print "App Name must be all lowercase and without spaces"
				hook_val = ""
		
		hooks[hook_key] = hook_val
		
	webnotes.create_folder(os.path.join(hooks.app_name, hooks.app_name, hooks.app_name))
	webnotes.create_folder(os.path.join(hooks.app_name, hooks.app_name, "templates"))
	webnotes.create_folder(os.path.join(hooks.app_name, hooks.app_name, "config"))
	touch_file(os.path.join(hooks.app_name, hooks.app_name, "__init__.py"))
	touch_file(os.path.join(hooks.app_name, hooks.app_name, hooks.app_name, "__init__.py"))
	touch_file(os.path.join(hooks.app_name, hooks.app_name, "templates", "__init__.py"))
	touch_file(os.path.join(hooks.app_name, hooks.app_name, "config", "__init__.py"))
	
	with open(os.path.join(hooks.app_name, "MANIFEST.in"), "w") as f:
		f.write(manifest_template.format(**hooks))

	with open(os.path.join(hooks.app_name, ".gitignore"), "w") as f:
		f.write(gitignore_template)

	with open(os.path.join(hooks.app_name, "setup.py"), "w") as f:
		f.write(setup_template.format(**hooks))

	with open(os.path.join(hooks.app_name, "requirements.txt"), "w") as f:
		f.write("webnotes")

	touch_file(os.path.join(hooks.app_name, "README.md"))

	with open(os.path.join(hooks.app_name, "license.txt"), "w") as f:
		f.write("License: " + hooks.app_license)

	with open(os.path.join(hooks.app_name, hooks.app_name, "modules.txt"), "w") as f:
		f.write(hooks.app_name)

	with open(os.path.join(hooks.app_name, hooks.app_name, "hooks.txt"), "w") as f:
		f.write(hooks_template.format(**hooks))

	touch_file(os.path.join(hooks.app_name, hooks.app_name, "patches.txt"))

	with open(os.path.join(hooks.app_name, hooks.app_name, "config", "desktop.py"), "w") as f:
		f.write(desktop_template.format(**hooks))
		
	

	
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
	
hooks_template = """app_name = {app_name}
app_title = {app_title}
app_publisher = {app_publisher}
app_description = {app_description}
app_icon = {app_icon}
app_color = {app_color}
app_email = {app_email}
app_url = {app_url}
app_version = 0.0.1
"""

desktop_template = """from webnotes import _

data = {{
	"{app_title}": {{
		"color": "{app_color}", 
		"icon": "{app_icon}", 
		"label": _("{app_title}")
	}}
}}
"""

setup_template = """from setuptools import setup, find_packages
import os

version = '0.0.1'

setup(
    name='{app_name}',
    version=version,
    description='{app_description}',
    author='{app_publisher}',
    author_email='{app_email}',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=("webnotes",),
)
"""

gitignore_template = """.DS_Store
*.pyc
*.egg-info
*.swp
tags"""