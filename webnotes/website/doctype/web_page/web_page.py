# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import WebsiteGenerator
from webnotes import _

class DocType(WebsiteGenerator):
	def autoname(self):
		from webnotes.webutils import cleanup_page_name
		self.doc.name = cleanup_page_name(self.doc.title)
		
	def validate(self):
		for d in self.doclist.get({"parentfield": "toc"}):
			if d.web_page == self.doc.name:
				webnotes.throw('{web_page} "{name}" {not_in_own} {toc}'.format(
					web_page=_("Web Page"), name=d.web_page,
					not_in_own=_("cannot be in its own"), toc=_(self.meta.get_label("toc"))))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from webnotes.webutils import clear_cache
			clear_cache()
			
	def on_trash(self):
		# delete entry from Table of Contents of other pages
		WebsiteGenerator.on_trash(self)
		
		webnotes.conn.sql("""delete from `tabTable of Contents`
			where web_page=%s""", self.doc.name)
		
		# clear all cache if it has toc
		if self.doclist.get({"parentfield": "toc"}):
			from webnotes.webutils import clear_cache
			clear_cache()
