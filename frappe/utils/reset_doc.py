from __future__ import unicode_literals
import frappe
import json, os
from frappe.modules import scrub, get_module_path, utils
from frappe.custom.doctype.customize_form.customize_form import doctype_properties, docfield_properties
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.core.page.permission_manager.permission_manager import get_standard_permissions
from frappe.permissions import setup_custom_perms
from six.moves.urllib.request import urlopen

branch = 'develop'

def reset_all():
	for doctype in frappe.db.get_all('DocType', dict(custom=0)):
		print(doctype.name)
		reset_doc(doctype.name)

def reset_doc(doctype):
	'''
		doctype = name of the DocType that you want to reset
	'''
	# fetch module name
	module = frappe.db.get_value('DocType', doctype, 'module')
	app = utils.get_module_app(module)

	# get path for doctype's json and its equivalent git url
	doc_path = os.path.join(get_module_path(module), 'doctype', scrub(doctype), scrub(doctype)+'.json')
	try:
		git_link = '/'.join(['https://raw.githubusercontent.com/frappe',\
			app, branch, doc_path.split('apps/'+app)[1]])
		original_file = urlopen(git_link).read()
	except:
		print('Did not find {0} in {1}'.format(doctype, app))
		return

	# load local and original json objects
	local_doc = json.loads(open(doc_path, 'r').read())
	original_doc = json.loads(original_file)

	remove_duplicate_fields(doctype)
	set_property_setter(doctype, local_doc, original_doc)
	make_custom_fields(doctype, local_doc, original_doc)

	with open(doc_path, 'w+') as f:
		f.write(original_file)
		f.close()

	setup_perms_for(doctype)

	frappe.db.commit()

def remove_duplicate_fields(doctype):
	for field in frappe.db.sql('''select fieldname, count(1) as cnt from tabDocField where parent=%s group by fieldname having cnt > 1''', doctype):
		frappe.db.sql('delete from tabDocField where fieldname=%s and parent=%s limit 1', (field[0], doctype))
		print('removed duplicate {0} in {1}'.format(field[0], doctype))

def set_property_setter(doctype, local_doc, original_doc):
	''' compare doctype_properties and docfield_properties and create property_setter '''

	# doctype_properties reset
	for dp in doctype_properties:
		# make property_setter to mimic changes made in local json
		if dp in local_doc and dp not in original_doc:
			make_property_setter(doctype, '', dp, local_doc[dp], doctype_properties[dp], for_doctype=True)

	local_fields = get_fields_dict(local_doc)
	original_fields = get_fields_dict(original_doc)

	# iterate through field and properties of each of those field
	for docfield in original_fields:
		for prop in original_fields[docfield]:
			# skip fields that are not in local_fields
			if docfield not in local_fields: continue

			if prop in docfield_properties and prop in local_fields[docfield]\
				and original_fields[docfield][prop] != local_fields[docfield][prop]:
				# make property_setter equivalent of local changes
				make_property_setter(doctype, docfield, prop, local_fields[docfield][prop],\
					docfield_properties[prop])

def make_custom_fields(doctype, local_doc, original_doc):
	'''
		check fields and create a custom field equivalent for non standard fields
	'''
	local_fields, original_fields = get_fields_dict(local_doc), get_fields_dict(original_doc)
	local_fields = sorted(local_fields.items(), key=lambda x: x[1]['idx'])
	doctype_doc = frappe.get_doc('DocType', doctype)

	custom_docfield_properties, prev = get_custom_docfield_properties(), ""
	for field, field_dict in local_fields:
		df = {}
		if field not in original_fields:
			for prop in field_dict:
				if prop in custom_docfield_properties:
					df[prop] = field_dict[prop]

			df['insert_after'] = prev if prev else ''

			doctype_doc.fields = [d for d in doctype_doc.fields if d.fieldname != df['fieldname']]
			doctype_doc.update_children()

			create_custom_field(doctype, df)

		# set current field as prev field for next field
		prev = field

def get_fields_dict(doc):
	fields, idx = {}, 0
	for field in doc['fields']:
		field['idx'] = idx
		fields[field.get('fieldname')] = field
		idx += 1

	return fields

def get_custom_docfield_properties():
	fields_meta = frappe.get_meta('Custom Field').fields
	fields = {}
	for d in fields_meta:
		fields[d.fieldname] = d.fieldtype

	return fields


def setup_perms_for(doctype):
	perms = frappe.get_all('DocPerm', fields='*', filters=dict(parent=doctype), order_by='idx asc')
	# get default perms
	try:
		standard_perms = get_standard_permissions(doctype)
	except (IOError, KeyError):
		# no json file, doctype no longer exists!
		return

	same = True
	if len(standard_perms) != len(perms):
		same = False

	else:
		for i, p in enumerate(perms):
			standard = standard_perms[i]
			for fieldname in frappe.get_meta('DocPerm').get_fieldnames_with_value():
				if p.get(fieldname) != standard.get(fieldname):
					same = False
					break

			if not same:
				break

	if not same:
		setup_custom_perms(doctype)