# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def update(ml):
	"""update modules"""
	webnotes.conn.set_global('hidden_modules', ml)
	webnotes.msgprint('Updated')
	webnotes.clear_cache()