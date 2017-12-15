# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
from six.moves import range
import frappe
from frappe.utils import cstr
from frappe.build import html_to_js_template
import re
from six import text_type


"""
Model utilities, unclassified functions
"""

def set_default(doc, key):
	"""Set is_default property of given doc and unset all others filtered by given key."""
	if not doc.is_default:
		frappe.db.set(doc, "is_default", 1)

	frappe.db.sql("""update `tab%s` set `is_default`=0
		where `%s`=%s and name!=%s""" % (doc.doctype, key, "%s", "%s"),
		(doc.get(key), doc.name))

def set_field_property(filters, key, value):
	'''utility set a property in all fields of a particular type'''
	docs = [frappe.get_doc('DocType', d.parent) for d in \
		frappe.get_all("DocField", fields=['parent'], filters=filters)]

	for d in docs:
		d.get('fields', filters)[0].set(key, value)
		d.save()
		print('Updated {0}'.format(d.name))

	frappe.db.commit()

class InvalidIncludePath(frappe.ValidationError): pass

def render_include(content):
	'''render {% raw %}{% include "app/path/filename" %}{% endraw %} in js file'''

	content = cstr(content)

	# try 5 levels of includes
	for i in range(5):
		if "{% include" in content:
			paths = re.findall(r'''{% include\s['"](.*)['"]\s%}''', content)
			if not paths:
				frappe.throw('Invalid include path', InvalidIncludePath)

			for path in paths:
				app, app_path = path.split('/', 1)
				with open(frappe.get_app_path(app, app_path), 'r') as f:
					include = text_type(f.read(), 'utf-8')
					if path.endswith('.html'):
						include = html_to_js_template(path, include)

					content = re.sub(r'''{{% include\s['"]{0}['"]\s%}}'''.format(path), include, content)

		else:
			break

	return content

def get_fetch_values(doctype, fieldname, value):
	'''Returns fetch value dict for the given object

	:param doctype: Target doctype
	:param fieldname: Link fieldname selected
	:param value: Value selected
	'''
	out = {}
	meta = frappe.get_meta(doctype)
	link_df = meta.get_field(fieldname)
	for df in meta.get_fields_to_fetch(fieldname):
		# example shipping_address.gistin
		link_field, source_fieldname = df.options.split('.', 1)
		out[df.fieldname] = frappe.db.get_value(link_df.options, value, source_fieldname)

	return out
