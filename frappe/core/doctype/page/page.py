# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.build import html_to_js_template
from frappe import conf, _
from frappe.desk.form.meta import get_code_files_via_hooks, get_js

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
		if self.is_new() and not getattr(conf,'developer_mode', 0):
			frappe.throw(_("Not in Developer Mode"))
		if frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator can edit"))

	# export
	def on_update(self):
		"""
			Writes the .txt for this page and if write_content is checked,
			it will write out a .html file
		"""
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

	def is_permitted(self):
		"""Returns true if Page Role is not set or the user is allowed."""
		from frappe.utils import has_common

		allowed = [d.role for d in frappe.get_all("Page Role", fields=["role"],
			filters={"parent": self.name})]

		if not allowed:
			return True

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

	def load_assets(self):
		from frappe.modules import get_module_path, scrub
		import os

		page_name = scrub(self.name)

		path = os.path.join(get_module_path(self.module), 'page', page_name)

		# script
		fpath = os.path.join(path, page_name + '.js')
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				self.script = unicode(f.read(), "utf-8")

		# css
		fpath = os.path.join(path, page_name + '.css')
		if os.path.exists(fpath):
			with open(fpath, 'r') as f:
				self.style = unicode(f.read(), "utf-8")

		# html as js template
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname), 'r') as f:
					template = unicode(f.read(), "utf-8")
					if "<!-- jinja -->" in template:
						context = {}
						try:
							context = frappe.get_attr("{app}.{module}.page.{page}.{page}.get_context".format(
								app = frappe.local.module_app[scrub(self.module)],
								module = scrub(self.module),
								page = page_name
							))(context)
						except (AttributeError, ImportError):
							pass

						template = frappe.render_template(template, context)
					self.script = html_to_js_template(fname, template) + self.script

		if frappe.lang != 'en':
			from frappe.translate import get_lang_js
			self.script += get_lang_js("page", self.name)

		for path in get_code_files_via_hooks("page_js", self.name):
			js = get_js(path)
			if js:
				self.script += "\n\n" + js


