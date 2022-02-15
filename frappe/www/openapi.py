import inspect

import frappe
from frappe import _dict

no_cache = 1
base_template_path = "www/openapi.yaml"


def get_context(context):
	context.methods = get_whitelisted_methods()
	context.resources = get_resources()

	return context


def get_whitelisted_methods():
	return [
		_dict(
			name=method.__name__,  # TODO: get the dotted.path.to.method instead
			parameters=[
				_dict(
					name=param.name,
					default=str(param.default) if not param.empty else None,
				)
				for param in inspect.signature(method).parameters.values()
			],
		)
		for method in frappe.whitelisted
	]


def get_resources():
	result = []
	for doctype in frappe.get_list("DocType", filters={"istable": 0}, pluck="name"):
		result.append(get_resource(doctype))
	return result


def get_resource(doctype: str):
	return _dict(
		name=doctype,
		properties=get_properties(doctype),
	)


def get_properties(doctype):
	EXCLUDED_FIELDTYPES = [
		"Section Break",
		"Column Break",
		"Button",
		"Read Only",
		"Fold",
		"Tab Break",
	]
	properties = []
	for field in frappe.get_meta(doctype).fields:
		if field.fieldtype in EXCLUDED_FIELDTYPES:
			continue
		prop = _dict(
			name=field.fieldname,
		)
		prop.update(get_openapi_type(field))
		properties.append(prop)

	return properties


def get_openapi_type(field):
	if field.fieldtype in [
		"Attach",
		"Attach Image",
		"Barcode",
		"Code",
		"Color",
		"Data",
		"Date",
		"Datetime",
		"Dynamic Link",
		"Geolocation",
		"Heading",
		"HTML",
		"HTML Editor",
		"Icon",
		"Image",
		"Link",
		"Long Text",
		"Markdown Editor",
		"Password",
		"Select",
		"Signature",
		"Small Text",
		"Text",
		"Text Editor",
		"Time",
	]:
		return _dict(type="string")
	elif field.fieldtype in [
		"Check",
		"Duration",
		"Int",
		"Rating",
		"Percent",
	]:
		return _dict(type="integer")
	elif field.fieldtype in [
		"Currency",
		"Float",
	]:
		return _dict(type="number")
	elif field.fieldtype in ["Table", "Table MultiSelect"]:
		return _dict(type="array", properties=get_properties(field.options))
