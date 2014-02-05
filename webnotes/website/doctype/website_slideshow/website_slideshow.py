# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		# a slide show can be in use and any change in it should get reflected
		from webnotes.webutils import clear_cache
		clear_cache()
		
def get_slideshow(bean):
	slideshow = webnotes.bean("Website Slideshow", bean.doc.slideshow)
	
	return {
		"slides": slideshow.doclist.get({"doctype":"Website Slideshow Item"}),
		"slideshow_header": slideshow.doc.header or ""
	}
