# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

# make public folders

from __future__ import unicode_literals
import os

def make():
	"""make public folder symlinks if missing"""
	
	dirs = ["public", "public/js", "public/css", "public/files", "public/backups"]
	
	for dirname in dirs:
		if not os.path.exists(dirname):
			os.mkdir(dirname)
	
	os.chdir("public")
	
	symlinks = [
		["app", "../app/public"],
		["lib", "../lib/public"],
		["unsupported.html", "../lib/public/html/unsupported.html"]
	]

	for link in symlinks:
		if not os.path.exists(link[0]) and os.path.exists(link[1]):
			os.symlink(link[1], link[0])

	os.chdir('..')
