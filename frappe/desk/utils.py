# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

import frappe


def convert_mariadb_to_orcaledb(string):
	if not frappe.is_oracledb:
		return string
	pattern = '`(?P<alias>\w+( \w+)*)`.`?(?P<column>\w+)`?'
	is_replace = False
	while _match := re.search(pattern=pattern, string=string):
		alias, column = _match.groupdict().values()
		template = '{alias}."{column}"'.format(alias=alias.replace(' ', '_'), column=column)
		string = string.replace(string[_match.start():_match.end()], template)
		is_replace = True
	if is_replace:
		return string

	if re.search('\w+\."\w+"', string):
		return string
	elif re.search('"\w+"', string):
		return string
	return f'"{string}"'


def convert_list(fields: list):
	return [
		convert_mariadb_to_orcaledb(string=string)
		for string in fields
	]

def convert_fields(fields: dict):
	fields['fields'] = convert_list(fields['fields'])

	if frappe.is_oracledb:
		if fields.get("order_by"):
			# if multiple orderby pass.
			order_by = []
			for order_by_clause in fields.get("order_by").split(","):
				if re.search(' asc$', order_by_clause, re.IGNORECASE):
					order_by.append(
						convert_mariadb_to_orcaledb(order_by_clause[:-4]) + ' asc'
					)
				elif re.search(' desc$', order_by_clause, re.IGNORECASE):
					order_by.append(
						convert_mariadb_to_orcaledb(order_by_clause[:-5]) + ' desc'
					)
				else:
					order_by.append(
						convert_mariadb_to_orcaledb(order_by_clause)
					)
			fields["order_by"] = ", ".join(order_by)


			# fields["order_by"] = f"{convert_mariadb_to_orcaledb(string=string[0])} {string[1]}"


def validate_route_conflict(doctype, name):
	"""
	Raises exception if name clashes with routes from other documents for /app routing
	"""

	if frappe.flags.in_migrate:
		return

	all_names = []
	for _doctype in ["Page", "Workspace", "DocType"]:
		all_names.extend(
			[slug(d) for d in frappe.get_all(_doctype, pluck="name") if (doctype != _doctype and d != name)]
		)

	if slug(name) in all_names:
		frappe.msgprint(frappe._("Name already taken, please set a new name"))
		raise frappe.NameError


def slug(name):
	return name.lower().replace(" ", "-")


def pop_csv_params(form_dict):
	"""Pop csv params from form_dict and return them as a dict."""
	from csv import QUOTE_NONNUMERIC

	from frappe.utils.data import cint, cstr

	return {
		"delimiter": cstr(form_dict.pop("csv_delimiter", ","))[0],
		"quoting": cint(form_dict.pop("csv_quoting", QUOTE_NONNUMERIC)),
	}


def get_csv_bytes(data: list[list], csv_params: dict) -> bytes:
	"""Convert data to csv bytes."""
	from csv import writer
	from io import StringIO

	file = StringIO()
	csv_writer = writer(file, **csv_params)
	csv_writer.writerows(data)

	return file.getvalue().encode("utf-8")


def provide_binary_file(filename: str, extension: str, content: bytes) -> None:
	"""Provide a binary file to the client."""
	from frappe import _

	frappe.response["type"] = "binary"
	frappe.response["filecontent"] = content
	frappe.response["filename"] = f"{_(filename)}.{extension}"
