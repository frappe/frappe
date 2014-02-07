# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes, json, os
from webnotes import _

@webnotes.whitelist()
def get():
	setup = []
	for app in webnotes.get_installed_apps():
		try:
			setup += webnotes.get_attr(app + ".config.setup.data")
		except ImportError, e:
			pass

	return setup
