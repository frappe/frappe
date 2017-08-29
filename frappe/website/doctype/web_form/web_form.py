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
from frappe.utils.file_manager import get_max_file_size
from frappe.modules.utils import export_module_json, get_doc_module
from six.moves.urllib.parse import urlencode
from frappe.integrations.utils import get_payment_gateway_controller
from six import iteritems


class WebForm(WebsiteGenerator):
	website = frappe._dict(
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

		if not frappe.flags.in_import:
			self.validate_fields()

		if self.accept_payment:
			self.validate_payment_amount()

	def validate_fields(self):
		'''Validate all fields are present'''
		from frappe.model import no_value_fields
		missing = []
		meta = frappe.get_meta(self.doc_type)
		for df in self.web_form_fields:
			if df.fieldname and (df.fieldtype not in no_value_fields and not meta.has_field(df.fieldname)):
				missing.append(df.fieldname)

		if missing:
			frappe.throw(_('Following fields are missing:') + '<br>' + '<br>'.join(missing))

	def validate_payment_amount(self):
		if self.amount_based_on_field and not self.amount_field:
			frappe.throw(_("Please select a Amount Field."))
		elif not self.amount_based_on_field and not self.amount > 0:
			frappe.throw(_("Amount must be greater than 0."))


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
		path = export_module_json(self, self.is_standard, self.module)

		if path:
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
		'''Build context to render the `web_form.html` template'''
		self.set_web_form_module()

		context._login_required = False
		if self.login_required and frappe.session.user == "Guest":
			context._login_required = True

		doc, delimeter = make_route_string(frappe.form_dict)
		context.doc = doc
		context.delimeter = delimeter

		# check permissions
		if frappe.session.user == "Guest" and frappe.form_dict.name:
			frappe.throw(_("You need to be logged in to access this {0}.").format(self.doc_type), frappe.PermissionError)

		if frappe.form_dict.name and not has_web_form_permission(self.doc_type, frappe.form_dict.name):
			frappe.throw(_("You don't have the permissions to access this document"), frappe.PermissionError)

		self.reset_field_parent()

		if self.is_standard:
			self.use_meta_fields()

		if not context._login_required:
			if self.allow_edit:
				if self.allow_multiple:
					if not frappe.form_dict.name and not frappe.form_dict.new:
						self.build_as_list(context)
				else:
					if frappe.session.user != 'Guest' and not frappe.form_dict.name:
						frappe.form_dict.name = frappe.db.get_value(self.doc_type, {"owner": frappe.session.user}, "name")

					if not frappe.form_dict.name:
						# only a single doc allowed and no existing doc, hence new
						frappe.form_dict.new = 1

		# always render new form if login is not required or doesn't allow editing existing ones
		if not self.login_required or not self.allow_edit:
			frappe.form_dict.new = 1

		self.load_document(context)
		context.parents = self.get_parents(context)

		if self.breadcrumbs:
			context.parents = frappe.safe_eval(self.breadcrumbs, { "_": _ })

		context.has_header = ((frappe.form_dict.name or frappe.form_dict.new)
			and (frappe.session.user!="Guest" or not self.login_required))

		if context.success_message:
			context.success_message = frappe.db.escape(context.success_message.replace("\n",
				"<br>"))

		self.add_custom_context_and_script(context)
		if not context.max_attachment_size:
			context.max_attachment_size = get_max_file_size() / 1024 / 1024

	def load_document(self, context):
		'''Load document `doc` and `layout` properties for template'''
		if frappe.form_dict.name or frappe.form_dict.new:
			context.layout = self.get_layout()
			context.parents = [{"route": self.route, "label": _(self.title) }]

		if frappe.form_dict.name:
			context.doc = frappe.get_doc(self.doc_type, frappe.form_dict.name)
			context.title = context.doc.get(context.doc.meta.get_title_field())
			context.doc.add_seen()

			context.reference_doctype = context.doc.doctype
			context.reference_name = context.doc.name

			if self.allow_comments:
				context.comment_list = get_comment_list(context.doc.doctype,
					context.doc.name)

	def build_as_list(self, context):
		'''Web form is a list, show render as list.html'''
		from frappe.www.list import get_context as get_list_context

		# set some flags to make list.py/list.html happy
		frappe.form_dict.web_form_name = self.name
		frappe.form_dict.doctype = self.doc_type
		frappe.flags.web_form = self

		self.update_params_from_form_dict(context)
		self.update_list_context(context)
		get_list_context(context)
		context.is_list = True

	def update_params_from_form_dict(self, context):
		'''Copy params from list view to new view'''
		context.params_from_form_dict = ''

		params = {}
		for key, value in iteritems(frappe.form_dict):
			if frappe.get_meta(self.doc_type).get_field(key):
				params[key] = value

		if params:
			context.params_from_form_dict = '&' + urlencode(params)


	def update_list_context(self, context):
		'''update list context for stanard modules'''
		if hasattr(self, 'web_form_module') and hasattr(self.web_form_module, 'get_list_context'):
			self.web_form_module.get_list_context(context)

	def get_payment_gateway_url(self, doc):
		if self.accept_payment:
			controller = get_payment_gateway_controller(self.payment_gateway)

			title = "Payment for {0} {1}".format(doc.doctype, doc.name)
			amount = self.amount
			if self.amount_based_on_field:
				amount = doc.get(self.amount_field)
			payment_details = {
				"amount": amount,
				"title": title,
				"description": title,
				"reference_doctype": doc.doctype,
				"reference_docname": doc.name,
				"payer_email": frappe.session.user,
				"payer_name": frappe.utils.get_fullname(frappe.session.user),
				"order_id": doc.name,
				"currency": self.currency,
				"redirect_to": frappe.utils.get_url(self.route)
			}

			# Redirect the user to this url
			return controller.get_payment_url(**payment_details)

	def add_custom_context_and_script(self, context):
		'''Update context from module if standard and append script'''
		if self.web_form_module:
			new_context = self.web_form_module.get_context(context)

			if new_context:
				context.update(new_context)

			js_path = os.path.join(os.path.dirname(self.web_form_module.__file__), scrub(self.name) + '.js')
			if os.path.exists(js_path):
				context.script = open(js_path, 'r').read()

			css_path = os.path.join(os.path.dirname(self.web_form_module.__file__), scrub(self.name) + '.css')
			if os.path.exists(css_path):
				context.style = open(css_path, 'r').read()

	def get_layout(self):
		layout = []
		def add_page(df=None):
			new_page = {'sections': []}
			layout.append(new_page)
			if df and df.fieldtype=='Page Break':
				new_page.update(df.as_dict())

			return new_page

		def add_section(df=None):
			new_section = {'columns': []}
			layout[-1]['sections'].append(new_section)
			if df and df.fieldtype=='Section Break':
				new_section.update(df.as_dict())

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
				if column==None:
					column = add_column()
				column.append(df)

		return layout

	def get_parents(self, context):
		parents = None

		if context.is_list and not context.parents:
			parents = [{"title": _("My Account"), "name": "me"}]
		elif context.parents:
			parents = context.parents

		return parents

	def set_web_form_module(self):
		'''Get custom web form module if exists'''
		if self.is_standard:
			self.web_form_module = get_doc_module(self.module, self.doctype, self.name)
		else:
			self.web_form_module = None

	def validate_mandatory(self, doc):
		'''Validate mandatory web form fields'''
		missing = []
		for f in self.web_form_fields:
			if f.reqd and doc.get(f.fieldname) in (None, [], ''):
				missing.append(f)

		if missing:
			frappe.throw(_('Mandatory Information missing:') + '<br><br>'
				+ '<br>'.join(['{0} ({1})'.format(d.label, d.fieldtype) for d in missing]))


@frappe.whitelist(allow_guest=True)
def accept(web_form, data, for_payment=False):
	'''Save the web form'''
	data = frappe._dict(json.loads(data))
	files = []
	files_to_delete = []

	web_form = frappe.get_doc("Web Form", web_form)
	if data.doctype != web_form.doc_type:
		frappe.throw(_("Invalid Request"))

	elif data.name and not web_form.allow_edit:
		frappe.throw(_("You are not allowed to update this Web Form Document"))

	frappe.flags.in_web_form = True

	if data.name:
		# update
		doc = frappe.get_doc(data.doctype, data.name)
	else:
		# insert
		doc = frappe.new_doc(data.doctype)

	# set values
	for fieldname, value in iteritems(data):
		if value and isinstance(value, dict):
			try:
				if "__file_attachment" in value:
					files.append((fieldname, value))
					continue
				if '__no_attachment' in value:
					files_to_delete.append(doc.get(fieldname))
					value = ''

			except ValueError:
				pass

		doc.set(fieldname, value)

	if for_payment:
		web_form.validate_mandatory(doc)
		doc.run_method('validate_payment')

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

			# remove earlier attached file (if exists)
			if doc.get(fieldname):
				remove_file_by_url(doc.get(fieldname), doc.doctype, doc.name)

			# save new file
			filedoc = save_file(filedata["filename"], filedata["dataurl"],
				doc.doctype, doc.name, decode=True)

			# update values
			doc.set(fieldname, filedoc.file_url)

		doc.save()

	if files_to_delete:
		for f in files_to_delete:
			if f:
				remove_file_by_url(f, doc.doctype, doc.name)

	frappe.flags.web_form_doc = doc

	if for_payment:
		return web_form.get_payment_gateway_url(doc)
	else:
		return doc.name

@frappe.whitelist()
def delete(web_form, name):
	web_form = frappe.get_doc("Web Form", web_form)

	owner = frappe.db.get_value(web_form.doc_type, name, "owner")
	if frappe.session.user == owner and web_form.allow_delete:
		frappe.delete_doc(web_form.doc_type, name, ignore_permissions=True)
	else:
		raise frappe.PermissionError("Not Allowed")

def has_web_form_permission(doctype, name, ptype='read'):
	if frappe.session.user=="Guest":
		return False

	# owner matches
	elif frappe.db.get_value(doctype, name, "owner")==frappe.session.user:
		return True

	elif frappe.has_website_permission(name, ptype=ptype, doctype=doctype):
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

def get_web_form_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by=None):
	from frappe.www.list import get_list
	if not filters:
		filters = {}

	filters["owner"] = frappe.session.user

	return get_list(doctype, txt, filters, limit_start, limit_page_length, order_by=order_by,
		ignore_permissions=True)

def make_route_string(parameters):
	route_string = ""
	delimeter = '?'
	if isinstance(parameters, dict):
		for key in parameters:
			if key != "web_form_name":
				route_string += route_string + delimeter + key + "=" + cstr(parameters[key])
				delimeter = '&'
	return (route_string, delimeter)