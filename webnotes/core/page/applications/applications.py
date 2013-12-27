# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def get_app_list():
	out = {}
	installed = webnotes.get_installed_apps()
	for app in webnotes.get_all_apps(True):
		out[app] = {}
		app_hooks = webnotes.get_hooks(app)
		for key in ("app_name", "app_title", "app_description", "app_icon",
			"app_publisher", "app_version", "app_url", "app_color"):
			out[app][key] = app_hooks.get(key)
			
		if app in installed:
			out[app]["installed"] = 1
		
	return out
