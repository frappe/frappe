# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import render_blocks

no_cache = 1
no_sitemap = 1

def get_context(context):
	message_context = {}
	if hasattr(webnotes.local, "message"):
		message_context["title"] = webnotes.local.message_title
		message_context["message"] = webnotes.local.message
		if hasattr(webnotes.local, "message_success"):
			message_context["success"] = webnotes.local.message_success
	
	message_context.update(context)
	return render_blocks(message_context)
