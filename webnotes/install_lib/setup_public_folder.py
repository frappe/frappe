# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# make public folders

from __future__ import unicode_literals
import os
import webnotes

def make(site=None):
	"""make public folder symlinks if missing"""
	from webnotes.utils import get_site_base_path, get_base_path, get_path
	
	webnotes.init(site=site)
	
	site_path = get_site_base_path() if site else get_base_path()
	
	# setup standard folders
	for param in (("public_path", "public"), ("backup_path", "public/backups"), ("files_path", "public/files")):
		path = os.path.join(site_path, webnotes.conf.get(param[0], param[1]))
		if not os.path.exists(path):
			os.mkdir(path)
	
	# setup js and css folders
	if not site:
		for folder in ("js", "css"):
			path = get_path(webnotes.conf.get("public_path", "public"), folder)
			if not os.path.exists(path):
				os.mkdir(path)
		
		os.chdir(webnotes.conf.get("public_path", "public"))
		symlinks = [
			["app", "../app/public"],
			["lib", "../lib/public"],
		]

		for link in symlinks:
			if not os.path.exists(link[0]) and os.path.exists(link[1]):
				os.symlink(link[1], link[0])
				
		os.chdir("..")
