# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
from webnotes.webutils import render_blocks

no_sitemap = 1

def get_context(context):
	return render_blocks(context)
