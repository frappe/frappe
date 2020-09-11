# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_path
from os.path import join as join_path, exists as path_exists, abspath, splitext

class WebsiteTheme(Document):
	def validate(self):
		self.validate_if_customizable()
		self.render_theme()
		self.generate_bootstrap_theme()

	def on_update(self):
		if (not self.custom
			and frappe.local.conf.get('developer_mode')
			and not (frappe.flags.in_import or frappe.flags.in_test)):

			self.export_doc()

		self.clear_cache_if_current_theme()

	def is_standard_and_not_valid_user(self):
		return (not self.custom
			and not frappe.local.conf.get('developer_mode')
			and not (frappe.flags.in_import or frappe.flags.in_test or frappe.flags.in_migrate))

	def on_trash(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("You are not allowed to delete a standard Website Theme"),
				frappe.PermissionError)

	def validate_if_customizable(self):
		if self.is_standard_and_not_valid_user():
			frappe.throw(_("Please Duplicate this Website Theme to customize."))

	def render_theme(self):
		self.theme_scss = frappe.render_template('frappe/website/doctype/website_theme/website_theme_template.scss', self.as_dict())

	def export_doc(self):
		"""Export to standard folder `[module]/website_theme/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files
		export_to_files(record_list=[['Website Theme', self.name]], create_init=True)


	def clear_cache_if_current_theme(self):
		if frappe.flags.in_install == 'frappe': return
		website_settings = frappe.get_doc("Website Settings", "Website Settings")
		if getattr(website_settings, "website_theme", None) == self.name:
			website_settings.clear_cache()

	def generate_bootstrap_theme(self):
		from subprocess import Popen, PIPE

		# create theme file in site public files folder
		folder_path = abspath(frappe.utils.get_files_path('website_theme', is_private=False))
		# create folder if not exist
		frappe.create_folder(folder_path)

		if not self.custom:
			self.delete_old_theme_files(folder_path)

		# add a random suffix
		suffix = frappe.generate_hash('Website Theme', 8) if self.custom else 'style'
		file_name = frappe.scrub(self.name) + '_' + suffix + '.css'
		output_path = join_path(folder_path, file_name)

		self.theme_scss = content = get_scss(self)
		content = content.replace('\n', '\\n')
		command = ['node', 'generate_bootstrap_theme.js', output_path, content]

		process = Popen(command, cwd=frappe.get_app_path('frappe', '..'), stdout=PIPE, stderr=PIPE)

		stderr = process.communicate()[1]

		if stderr:
			stderr = frappe.safe_decode(stderr)
			stderr = stderr.replace('\n', '<br>')
			frappe.throw('<div style="font-family: monospace;">{stderr}</div>'.format(stderr=stderr))
		else:
			self.theme_url = '/files/website_theme/' + file_name

		frappe.msgprint(_('Compiled Successfully'), alert=True)

	def delete_old_theme_files(self, folder_path):
		import os
		for fname in os.listdir(folder_path):
			if fname.startswith(frappe.scrub(self.name) + '_') and fname.endswith('.css'):
				os.remove(os.path.join(folder_path, fname))

	def generate_theme_if_not_exist(self):
		bench_path = frappe.utils.get_bench_path()
		if self.theme_url:
			theme_path = join_path(bench_path, 'sites', self.theme_url[1:])
			if not path_exists(theme_path):
				self.generate_bootstrap_theme()
		else:
			self.generate_bootstrap_theme()

	def set_as_default(self):
		website_settings = frappe.get_doc('Website Settings')
		website_settings.website_theme = self.name
		website_settings.ignore_validate = True
		website_settings.save()

def add_website_theme(context):
	context.theme = frappe._dict()

	if not context.disable_website_theme:
		website_theme = get_active_theme()
		context.theme = website_theme or frappe._dict()

def get_active_theme():
	website_theme = frappe.db.get_single_value("Website Settings", "website_theme")
	if website_theme:
		try:
			return frappe.get_doc("Website Theme", website_theme)
		except frappe.DoesNotExistError:
			pass


def get_scss(website_theme):
	"""
	Render `website_theme_template.scss` with the values defined in Website Theme.

	params:
	website_theme - instance of a Website Theme
	"""
	list_of_imports_to_ignore = (website_theme.get('imports_to_ignore') or '').split(',')
	set_of_imports_to_ignore = {s.strip() for s in list_of_imports_to_ignore}
	set_of_available_imports = get_scss_paths()

	opts = website_theme.as_dict()
	opts['website_theme_scss'] = set_of_available_imports.difference(set_of_imports_to_ignore)
	return frappe.render_template('frappe/website/doctype/website_theme/website_theme_template.scss', opts)


def get_scss_paths():
	"""
	Return a set of SCSS import paths from all apps that provide `website.scss`.

	If `$BENCH_PATH/apps/frappe/frappe/public/scss/website.scss` exists, the
	returned set will contain 'frappe/public/scss/website'.
	"""
	import_path_list = set()
	bench_path = frappe.utils.get_bench_path()

	for app in frappe.get_installed_apps():
		relative_path = join_path(app, 'public/scss/website.scss')
		full_path = get_path('apps', app, relative_path, base=bench_path)
		if path_exists(full_path):
			import_path = splitext(relative_path)[0]
			import_path_list.add(import_path)

	return import_path_list
