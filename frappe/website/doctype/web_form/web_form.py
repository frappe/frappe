# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json, os
from frappe.website.website_generator import WebsiteGenerator
from frappe import _, scrub
from frappe.utils import cstr
from frappe.utils.file_manager import save_file, remove_file_by_url
from frappe.website.utils import get_comment_list
from frappe.custom.doctype.customize_form.customize_form import docfield_properties
from frappe.integration_broker.doctype.integration_service.integration_service import get_integration_controller
from frappe.utils.file_manager import get_max_file_size

class WebForm(WebsiteGenerator):
	website = frappe._dict(
		template = "templates/generators/web_form.html",
		condition_field = "published",
		page_title_field = "title",
		no_cache = 1
	)

	def onload(self):
		super(WebForm, self).onload()
		if self.is_standard and not frappe.conf.developer_mode:
			self.use_meta_fields()

	def validate(self):
		super(WebForm, self).validate()

		if not self.module:
			self.module = frappe.db.get_value('DocType', self.doc_type, 'module')

		if (not (frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_test or frappe.flags.in_fixtures)
			and self.is_standard and not frappe.conf.developer_mode):
			frappe.throw(_("You need to be in developer mode to edit a Standard Web Form"))

	def reset_field_parent(self):
		'''Convert link fields to select with names as options'''
		for df in self.web_form_fields:
			df.parent = self.doc_type

	def use_meta_fields(self):
		'''Override default properties for standard web forms'''
		meta = frappe.get_meta(self.doc_type)

		for df in self.web_form_fields:
			meta_df = meta.get_field(df.fieldname)

			if not meta_df:
				continue

			for prop in docfield_properties:
				if df.fieldtype==meta_df.fieldtype and prop not in ("idx",
					"reqd", "default", "description", "default", "options",
					"hidden", "read_only", "label"):
					df.set(prop, meta_df.get(prop))


			# TODO translate options of Select fields like Country

	# export
	def on_update(self):
		"""
			Writes the .txt for this page and if write_content is checked,
			it will write out a .html file
		"""
		if not frappe.flags.in_import and getattr(frappe.get_conf(),'developer_mode', 0) and self.is_standard:
			from frappe.modules.export_file import export_to_files
			from frappe.modules import get_module_path

			# json
			export_to_files(record_list=[['Web Form', self.name]], record_module=self.module)

			# write files
			path = os.path.join(get_module_path(self.module), 'web_form', scrub(self.name), scrub(self.name))

			# js
			if not os.path.exists(path + '.js'):
				with open(path + '.js', 'w') as f:
					f.write("""frappe.ready(function() {
	// bind events here
})""")

			# py
			if not os.path.exists(path + '.py'):
				with open(path + '.py', 'w') as f:
					f.write("""from __future__ import unicode_literals

import frappe

def get_context(context):
	# do your magic here
	pass
""")

	def get_context(self, context):
		from frappe.www.list import get_context as get_list_context

		frappe.form_dict.is_web_form = 1
		logged_in = frappe.session.user != "Guest"

		doc, delimeter = make_route_string(frappe.form_dict)
		context.doc = doc
		context.delimeter = delimeter

		# check permissions
		if not logged_in and frappe.form_dict.name:
			frappe.throw(_("You need to be logged in to access this {0}.").format(self.doc_type), frappe.PermissionError)

		if frappe.form_dict.name and not has_web_form_permission(self.doc_type, frappe.form_dict.name):
			frappe.throw(_("You don't have the permissions to access this document"), frappe.PermissionError)

		self.reset_field_parent()

		if self.is_standard:
			self.use_meta_fields()

		if self.login_required and logged_in:
			if self.allow_edit:
				if self.allow_multiple:
					if not frappe.form_dict.name and not frappe.form_dict.new:
						frappe.form_dict.doctype = self.doc_type
						get_list_context(context)
						context.is_list = True
				else:
					name = frappe.db.get_value(self.doc_type, {"owner": frappe.session.user}, "name")
					if name:
						frappe.form_dict.name = name
					else:
						# only a single doc allowed and no existing doc, hence new
						frappe.form_dict.new = 1

		# always render new form if login is not required or doesn't allow editing existing ones
		if not self.login_required or not self.allow_edit:
			frappe.form_dict.new = 1

		if frappe.form_dict.name or frappe.form_dict.new:
			context.layout = self.get_layout()
			context.parents = [{"route": self.route, "title": self.title }]

		if frappe.form_dict.name:
			context.doc = frappe.get_doc(self.doc_type, frappe.form_dict.name)
			context.title = context.doc.get(context.doc.meta.get_title_field())
			context.doc.add_seen()

			context.reference_doctype = context.doc.doctype
			context.reference_name = context.doc.name

		if self.allow_comments and frappe.form_dict.name:
			context.comment_list = get_comment_list(context.doc.doctype,
				context.doc.name)

		context.parents = self.get_parents(context)

		if self.breadcrumbs:
			context.parents = eval(self.breadcrumbs)

		context.has_header = ((frappe.form_dict.name or frappe.form_dict.new)
			and (frappe.session.user!="Guest" or not self.login_required))

		if context.success_message:
			context.success_message = context.success_message.replace("\n",
				"<br>").replace("'", "\'")

		self.add_custom_context_and_script(context)
		self.add_payment_gateway_url(context)
		context.max_attachment_size = get_max_file_size()

	def add_payment_gateway_url(self, context):
		if context.doc and self.accept_payment:
			controller = get_integration_controller(self.payment_gateway)

			title = "Payment for {0} {1}".format(context.doc.doctype, context.doc.name)

			payment_details = {
				"amount": self.amount,
				"title": title,
				"description": title,
				"reference_doctype": context.doc.doctype,
				"reference_docname": context.doc.name,
				"payer_email": frappe.session.user,
				"payer_name": frappe.utils.get_fullname(frappe.session.user),
				"order_id": context.doc.name,
				"currency": self.currency,
				"redirect_to": frappe.utils.get_url(self.route)
			}

			# Redirect the user to this url
			context.payment_url = controller.get_payment_url(**payment_details)

	def add_custom_context_and_script(self, context):
		'''Update context from module if standard and append script'''
		if self.is_standard:
			module_name = "{app}.{module}.web_form.{name}.{name}".format(
					app = frappe.local.module_app[scrub(self.module)],
					module = scrub(self.module),
					name = scrub(self.name)
			)
			module = frappe.get_module(module_name)
			new_context = module.get_context(context)

			if new_context:
				context.update(new_context)

			js_path = os.path.join(os.path.dirname(module.__file__), scrub(self.name) + '.js')
			if os.path.exists(js_path):
				context.script = open(js_path, 'r').read()

			css_path = os.path.join(os.path.dirname(module.__file__), scrub(self.name) + '.css')
			if os.path.exists(css_path):
				context.style = open(css_path, 'r').read()

	def get_layout(self):
		layout = []
		def add_page(df=None):
			new_page = {'sections': []}
			layout.append(new_page)
			if df and df.fieldtype=='Page Break':
				new_page['label'] = df.label

			return new_page

		def add_section(df=None):
			new_section = {'columns': []}
			layout[-1]['sections'].append(new_section)
			if df and df.fieldtype=='Section Break':
				new_section['label'] = df.label

			return new_section

		def add_column(df=None):
			new_col = []
			layout[-1]['sections'][-1]['columns'].append(new_col)

			return new_col

		page, section, column = None, None, None
		for df in self.web_form_fields:

			# breaks
			if df.fieldtype=='Page Break':
				page = add_page(df)
				section, column = None, None

			if df.fieldtype=='Section Break':
				section = add_section(df)
				column = None

			if df.fieldtype=='Column Break':
				column = add_column(df)

			# input
			if df.fieldtype not in ('Section Break', 'Column Break', 'Page Break'):
				if not page:
					page = add_page()
					section, column = None, None
				if not section:
					section = add_section()
					column = None
				if not column:
					column = add_column()
				column.append(df)

		return layout

	def get_parents(self, context):
		parents = None

		if context.is_list:
			parents = [{"title": _("My Account"), "name": "me"}]
		elif context.parents:
			parents = context.parents

		return parents

@frappe.whitelist(allow_guest=True)
def accept(web_form, data):
	data = frappe._dict(json.loads(data))
	files = []

	web_form = frappe.get_doc("Web Form", web_form)
	if data.doctype != web_form.doc_type:
		frappe.throw(_("Invalid Request"))

	elif data.name and not web_form.allow_edit:
		frappe.throw(_("You are not allowed to update this Web Form Document"))

	if data.name:
		# update
		doc = frappe.get_doc(data.doctype, data.name)
	else:
		# insert
		doc = frappe.new_doc(data.doctype)

	# set values
	for fieldname, value in data.iteritems():
		if value and isinstance(value, dict):
			try:
				if "__file_attachment" in value:
					files.append((fieldname, value))
					continue

			except ValueError:
				pass

		doc.set(fieldname, value)

	if doc.name:
		if has_web_form_permission(doc.doctype, doc.name, "write"):
			doc.save(ignore_permissions=True)
		else:
			# only if permissions are present
			doc.save()

	else:
		# insert
		if web_form.login_required and frappe.session.user=="Guest":
			frappe.throw(_("You must login to submit this form"))

		doc.insert(ignore_permissions = True)

	# add files
	if files:
		for f in files:
			fieldname, filedata = f

			# remove earlier attachmed file (if exists)
			if doc.get(fieldname):
				remove_file_by_url(doc.get(fieldname), doc.doctype, doc.name)

			# save new file
			filedoc = save_file(filedata["filename"], filedata["dataurl"],
				doc.doctype, doc.name, decode=True)

			# update values
			doc.set(fieldname, filedoc.file_url)

		doc.save()

	return doc.name

@frappe.whitelist()
def delete(web_form, name):
	web_form = frappe.get_doc("Web Form", web_form)

	owner = frappe.db.get_value(web_form.doc_type, name, "owner")
	if frappe.session.user == owner and web_form.allow_delete:
		frappe.delete_doc(web_form.doc_type, name, ignore_permissions=True)
	else:
		raise frappe.PermissionError, "Not Allowed"

def has_web_form_permission(doctype, name, ptype='read'):
	if frappe.session.user=="Guest":
		return False

	# owner matches
	elif frappe.db.get_value(doctype, name, "owner")==frappe.session.user:
		return True

	elif frappe.has_website_permission(doctype, ptype=ptype, doc=name):
		return True

	elif check_webform_perm(doctype, name):
		return True

	else:
		return False


def check_webform_perm(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if hasattr(doc, "has_webform_permission"):
		if doc.has_webform_permission():
			return True

def get_web_form_list(doctype, txt, filters, limit_start, limit_page_length=20):
	from frappe.www.list import get_list
	if not filters:
		filters = {}

	filters["owner"] = frappe.session.user

	return get_list(doctype, txt, filters, limit_start, limit_page_length, ignore_permissions=True)

def make_route_string(parameters):
	route_string = ""
	delimeter = '?'
	if isinstance(parameters, dict):
		for key in parameters:
			if key != "is_web_form":
				route_string += route_string + delimeter + key + "=" + cstr(parameters[key])
				delimeter = '&'
	return (route_string, delimeter)