# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.build import html_to_js_template

class Page(Document):
	def autoname(self):
		"""
			Creates a url friendly name for this page.
			Will restrict the name to 30 characters, if there exists a similar name,
			it will add name-1, name-2 etc.
		"""
		from frappe.utils import cint
		if (self.name and self.name.startswith('New Page')) or not self.name:
			self.name = self.page_name.lower().replace('"','').replace("'",'').\
				replace(' ', '-')[:20]
			if frappe.db.exists('Page',self.name):
				cnt = frappe.db.sql("""select name from tabPage
					where name like "%s-%%" order by name desc limit 1""" % self.name)
				if cnt:
					cnt = cint(cnt[0][0].split('-')[-1]) + 1
				else:
					cnt = 1
				self.name += '-' + str(cnt)

	def validate(self):
		if not getattr(conf,'developer_mode', 0):
			frappe.throw(_("Not in Developer Mode"))

	# export
	def on_update(self):
		"""
			Writes the .txt for this page and if write_content is checked,
			it will write out a .html file
		"""
		from frappe import conf
		from frappe.core.doctype.doctype.doctype import make_module_and_roles
		make_module_and_roles(self, "roles")

		if not frappe.flags.in_import and getattr(conf,'developer_mode', 0) and self.standard=='Yes':
			from frappe.modules.export_file import export_to_files
			from frappe.modules import get_module_path, scrub
			import os
			export_to_files(record_list=[['Page', self.name]])

			# write files
			path = os.path.join(get_module_path(self.module), 'page', scrub(self.name), scrub(self.name))

			# js
			if not os.path.exists(path + '.js'):
				with open(path + '.js', 'w') as f:
					f.write("""frappe.pages['%s'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: '%s',
		single_column: true
	});
}""" % (self.name, self.title))

	def as_dict(self, no_nulls=False):
		d = super(Page, self).as_dict(no_nulls=no_nulls)
		for key in ("script", "style", "content"):
			d[key] = self.get(key)
		return d

	def load_assets(self):
		from frappe.modules import get_module_path, scrub
		import os

		path = os.path.join(get_module_path(self.module), 'page', scrub(self.name))

		# script
		fpath = os.path.join(path, scrub(self.name) + '.js')
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				self.script = unicode(f.read(), "utf-8")

		# css
		fpath = os.path.join(path, scrub(self.name) + '.css')
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				self.style = unicode(f.read(), "utf-8")

		# html as js template
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname), 'r') as f:
					template = unicode(f.read(), "utf-8")
					self.script = html_to_js_template(fname, template) + self.script

		if frappe.lang != 'en':
			from frappe.translate import get_lang_js
			self.script += get_lang_js("page", self.name)
