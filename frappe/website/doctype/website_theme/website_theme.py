# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.website.utils import get_website_name

class WebsiteTheme(Document):
	def validate(self):
		self.validate_if_customizable()
		self.validate_colors()

	def on_update(self):
		if (not self.custom
			and frappe.local.conf.get('developer_mode')
			and not (frappe.flags.in_import or frappe.flags.in_test)):

			self.export_doc()

		self.clear_cache_if_current_theme()

	def is_standard_and_not_valid_user(self):
		return (not self.custom
			and not frappe.local.conf.get('developer_mode')
			and not (frappe.flags.in_import or frappe.flags.in_test))

	def on_trash(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("You are not allowed to delete a standard Website Theme"),
				frappe.PermissionError)

	def validate_if_customizable(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("Please Duplicate this Website Theme to customize."))

	def validate_colors(self):
		if (self.top_bar_color or self.top_bar_text_color) and \
			self.top_bar_color==self.top_bar_text_color:
				frappe.throw(_("Top Bar Color and Text Color are the same. They should be have good contrast to be readable."))


	def export_doc(self):
		"""Export to standard folder `[module]/website_theme/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files
		export_to_files(record_list=[['Website Theme', self.name]], create_init=True)


	def clear_cache_if_current_theme(self):
		if not hasattr(frappe.local, 'request'):
			return
		
		website = frappe.get_doc('Website', get_website_name())
		if getattr(website, "website_theme", None) == self.name:
			website.clear_cache()

def add_website_theme(context):
	bootstrap = frappe.get_hooks("bootstrap")[0]
	bootstrap = [bootstrap]
	context.theme = frappe._dict()

	if not context.disable_website_theme:
		website_theme = get_active_theme()
		context.theme = website_theme and website_theme.as_dict() or frappe._dict()

		if website_theme:
			if website_theme.bootstrap:
				bootstrap.append(website_theme.bootstrap)

			context.web_include_css = context.web_include_css + ["website_theme.css"]

	context.web_include_css = bootstrap + context.web_include_css

def get_active_theme():
	website_theme = frappe.db.get_value('Website', get_website_name(), "website_theme")
	if website_theme:
		try:
			return frappe.get_doc("Website Theme", website_theme)
		except frappe.DoesNotExistError:
			pass
