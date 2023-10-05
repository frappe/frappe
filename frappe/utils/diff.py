import json
from difflib import unified_diff

import frappe
from frappe.utils import pretty_date
from frappe.utils.data import cstr


@frappe.whitelist()
def get_version_diff(
	from_version: int | str, to_version: int | str, fieldname: str = "script"
) -> list[str]:
	"""
 Return the difference between the values of the specified field in two versions.

		This function takes in two versions (from_version and to_version) and a
 fieldname as input and returns the difference between the values of the
 specified field in the two versions. The function first retrieves the values
 of the field from the specified versions using the _get_value_from_version()
 function. If the values are available, the function splits the values into
 lists of lines, and then uses the unified_diff() function from the difflib
 module to compute the difference between the lists of lines. The function
 returns the difference as a list of strings.

 Args:
  from_version (int|str): The starting version.
  to_version (int|str): The ending version.
  fieldname (str, optional): The name of the field to compare. Defaults to "script".

 Returns:
  list[str]: The difference between the values of the specified field in two
  versions.
 """

	before, before_timestamp = _get_value_from_version(from_version, fieldname)
	after, after_timestamp = _get_value_from_version(to_version, fieldname)

	if not (before and after):
		return ["Values not available for diff"]

	before = before.split("\n")
	after = after.split("\n")

	diff = unified_diff(
		before,
		after,
		fromfile=cstr(from_version),
		tofile=cstr(to_version),
		fromfiledate=before_timestamp,
		tofiledate=after_timestamp,
	)
	return list(diff)


def _get_value_from_version(version_name: int | str, fieldname: str):
	"""
 Return the value of the specified field in the specified version.

 This function takes in a version name and a fieldname as input and returns the value
 of the specified field in the specified version. The function retrieves the
 version data using the frappe.get_list() function and searches for the
 specified field in the changed fields list. If the field is found, the
 function returns the value of the field and the modified timestamp as a
 tuple. If the field is not found, the function returns none values.

 Args:
  version_name (int|str): The name of the version.
  fieldname (str): The name of the field to retrieve.

 Returns:
  tuple: The value of the specified field in the specified version and the
  modified timestamp as a tuple.
 """
	version = frappe.get_list("Version", fields=["data", "modified"], filters={"name": version_name})
	if version:
		data = json.loads(version[0].data)
		changed_fields = data.get("changed", [])

		# data structure of field: [fieldname, before_save, after_save]
		for field in changed_fields:
			if field[0] == fieldname:
				return field[2], str(version[0].modified)

	return None, None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def version_query(doctype, txt, searchfield, start, page_len, filters):
	"""
	Query the database for Version objects based on the provided arguments.

	This function retrieves a list of Version objects from the database and
	processes the results to return a formatted list of tuples.

	Args:
		doctype (str): The type of document to query.
		txt (str): The search text to filter the results.
		searchfield (str): The field to search for the search text.
		start (int): The starting index of the results.
		page_len (int): The number of results per page.
		filters (dict): Additional filters to apply to the query.

	Returns:
		list: A list of tuples, each containing the name, formatted modified
		date, and modified date of a Version object.
	"""
	results = frappe.get_list(
		"Version",
		fields=["name", "modified"],
		filters=filters,
		limit_start=start,
		limit_page_length=page_len,
		order_by="modified desc",
	)
	return [(d.name, pretty_date(d.modified), d.modified) for d in results]
