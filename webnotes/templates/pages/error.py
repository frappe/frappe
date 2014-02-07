# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

no_cache = 1
no_sitemap = 1

def get_context(context):
	return {"error": webnotes.get_traceback()}
