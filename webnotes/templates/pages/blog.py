# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _

def get_context(context):
	extended_context = webnotes.doc("Blog Settings", "Blog Settings").fields
	extended_context.update(context)
	
	return {
		"title": extended_context.blog_title or "Blog",
		"content": context.template.render(extended_context)
	}