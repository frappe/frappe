# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# make public folders

from __future__ import unicode_literals
import os
import webnotes

def make(public_path=None):
	"""make public folder symlinks if missing"""
	
	webnotes.init()

	if not public_path:
		public_path = 'public'
	
	# setup standard folders
	for dirs in ['backups', 'files', 'js', 'css']:
		dir_path = os.path.join(public_path, dirs)
		if not os.path.exists(dir_path):
			os.makedirs(dir_path)
	
	symlinks = []
	for app in webnotes.get_app_list():
		pymodule = webnotes.get_module(app)
		pymodule_path = os.path.abspath(os.path.dirname(pymodule.__file__))
		symlinks.append([app, os.path.join(pymodule_path, 'public')])

	for link in symlinks:
		if not os.path.exists(link[0]) and os.path.exists(link[1]):
			os.symlink(link[1], link[0])
