# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _, msgprint
from webnotes.model.controller import DocListController

class DocType(DocListController):
	def validate(self):
		self.validate_top_bar_items()
		self.validate_footer_items()
		self.validate_home_page()
	
	def validate_home_page(self):
		if self.doc.home_page and \
			not webnotes.conn.get_value("Website Sitemap", {"name": self.doc.home_page}):
			webnotes.throw(_("Invalid Home Page") + " (Standard pages - index, login, products, blog, about, contact)")
	
	def validate_top_bar_items(self):
		"""validate url in top bar items"""
		for top_bar_item in self.doclist.get({"parentfield": "top_bar_items"}):
			if top_bar_item.parent_label:
				parent_label_item = self.doclist.get({"parentfield": "top_bar_items", 
					"label": top_bar_item.parent_label})
				
				if not parent_label_item:
					# invalid item
					msgprint(_(self.meta.get_label("parent_label", parentfield="top_bar_items")) +
						(" \"%s\": " % top_bar_item.parent_label) + _("does not exist"), raise_exception=True)
				
				elif not parent_label_item[0] or parent_label_item[0].url:
					# parent cannot have url
					msgprint(_("Top Bar Item") + (" \"%s\": " % top_bar_item.parent_label) +
						_("cannot have a URL, because it has child item(s)"), raise_exception=True)
	
	def validate_footer_items(self):
		"""clear parent label in footer"""
		for footer_item in self.doclist.get({"parentfield": "footer_items"}):
			footer_item.parent_label = None

	def on_update(self):
		# make js and css
		# clear web cache (for menus!)

		from webnotes.webutils import clear_cache
		clear_cache()
			