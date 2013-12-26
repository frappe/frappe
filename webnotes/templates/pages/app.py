# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

no_cache = True
import webnotes, os

def get_context():
	hooks = webnotes.get_hooks()
	return {
		"build_version": str(os.path.getmtime(os.path.join(webnotes.local.sites_path, "assets", "js", 
			"webnotes.min.js"))),
		"include_js": hooks["app_include_js"],
		"include_css": hooks["app_include_css"]
	}