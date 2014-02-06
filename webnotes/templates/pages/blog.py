# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import render_blocks

def get_context(context):
	blog_context = webnotes.doc("Blog Settings", "Blog Settings").fields
	blog_context.update(context)
	return render_blocks(blog_context)
