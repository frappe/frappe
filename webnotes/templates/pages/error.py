# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import render_blocks

no_cache = 1
no_sitemap = 1

def get_context(context):
	error_context = {"error": webnotes.get_traceback()}
	error_context.update(context)
	
	return render_blocks(error_context)
