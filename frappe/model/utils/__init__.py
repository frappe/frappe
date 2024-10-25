# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re
from functools import wraps

import frappe
from frappe.build import html_to_js_template
from frappe.utils import cstr
from frappe.utils.caching import site_cache

STANDARD_FIELD_CONVERSION_MAP = {
	"name": "Link",
	"owner": "Data",
	"idx": "Int",
	"creation": "Data",
	"modified": "Data",
	"modified_by": "Data",
	"_user_tags": "Data",
	"_liked_by": "Data",
	"_comments": "Text",
	"_assign": "Text",
	"docstatus": "Int",
}
INCLUDE_DIRECTIVE_PATTERN = re.compile(r"""{% include\s['"](.*)['"]\s%}""")


def set_default(doc, key) -> None:
	"""Set is_default property of given doc and unset all others filtered by given key."""
	if not doc.is_default:
		frappe.db.set(doc, "is_default", 1)

	frappe.db.sql(
		"""update `tab{}` set `is_default`=0
		where `{}`={} and name!={}""".format(doc.doctype, key, "%s", "%s"),
		(doc.get(key), doc.name),
	)


def set_field_property(filters, key, value) -> None:
	"""utility set a property in all fields of a particular type"""
	docs = [
		frappe.get_doc("DocType", d.parent)
		for d in frappe.get_all("DocField", fields=["parent"], filters=filters)
	]

	for d in docs:
		d.get("fields", filters)[0].set(key, value)
		d.save()
		print(f"Updated {d.name}")

	frappe.db.commit()


class InvalidIncludePath(frappe.ValidationError):
	pass


def render_include(content):
	"""render {% raw %}{% include "app/path/filename" %}{% endraw %} in js file"""

	content = cstr(content)

	# try 5 levels of includes
	for _ in range(5):
		if "{% include" in content:
			paths = INCLUDE_DIRECTIVE_PATTERN.findall(content)
			if not paths:
				raise InvalidIncludePath

			for path in paths:
				app, app_path = path.split("/", 1)
				with open(frappe.get_app_path(app, app_path), encoding="utf-8") as f:
					include = f.read()
					if path.endswith(".html"):
						include = html_to_js_template(path, include)

					content = re.sub(
						rf"""{{% include\s['"]{path}['"]\s%}}""", include.replace("\\", "\\\\"), content
					)

		else:
			break

	return content


def get_fetch_values(doctype, fieldname, value):
	"""Return fetch value dict for the given object.

	:param doctype: Target doctype
	:param fieldname: Link fieldname selected
	:param value: Value selected
	"""

	result = frappe._dict()
	meta = frappe.get_meta(doctype)

	# fieldname in target doctype: fieldname in source doctype
	fields_to_fetch = {
		df.fieldname: df.fetch_from.split(".", 1)[1] for df in meta.get_fields_to_fetch(fieldname)
	}

	# nothing to fetch
	if not fields_to_fetch:
		return result

	# initialise empty values for target fields
	for target_fieldname in fields_to_fetch:
		result[target_fieldname] = None

	# fetch only if Link field has a truthy value
	if not value:
		return result

	db_values = frappe.db.get_value(
		meta.get_options(fieldname),  # source doctype
		value,
		tuple(set(fields_to_fetch.values())),  # unique source fieldnames
		as_dict=True,
	)

	# if value doesn't exist in source doctype, get_value returns None
	if not db_values:
		return result

	for target_fieldname, source_fieldname in fields_to_fetch.items():
		result[target_fieldname] = db_values.get(source_fieldname)

	return result


@site_cache()
def is_virtual_doctype(doctype: str):
	if frappe.flags.in_install or frappe.flags.in_migrate:
		if frappe.db.has_column("DocType", "is_virtual"):
			return frappe.db.get_value("DocType", doctype, "is_virtual")
	else:
		return getattr(frappe.get_meta(doctype), "is_virtual", False)


@site_cache()
def is_single_doctype(doctype: str) -> bool:
	from frappe.model.base_document import DOCTYPES_FOR_DOCTYPE

	if doctype in DOCTYPES_FOR_DOCTYPE:
		return False

	if frappe.flags.in_install or frappe.flags.in_migrate:
		return frappe.db.get_value("DocType", doctype, "issingle")
	else:
		return getattr(frappe.get_meta(doctype), "issingle", False)


def simple_singledispatch(func):
	registry = {}

	def dispatch(arg):
		for cls in arg.__class__.__mro__:
			if cls in registry:
				return registry[cls]
		return func

	def register(type_):
		def decorator(f):
			registry[type_] = f
			return f

		return decorator

	@wraps(func)
	def wrapper(*args, **kw):
		if not args:
			return func(*args, **kw)
		return dispatch(args[0])(*args, **kw)

	wrapper.register = register
	return wrapper
