# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import render_blocks

def get_context(context):
	about_context = {
		"obj": webnotes.bean("About Us Settings", "About Us Settings").get_controller()
	}
	
	about_context.update(context)
	return render_blocks(about_context)
