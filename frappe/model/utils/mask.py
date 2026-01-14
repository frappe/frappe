# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


def mask_field_value(field, val):
	"""Mask a field value based on its fieldtype and options.

	Args:
		field: DocField object with fieldtype and options attributes
		val: The value to mask

	Returns:
		Masked value based on field type, or original value if None/empty

	Masking patterns:
		- Phone (Data + Phone option): Shows first 3 chars + "XXXXXX"
		- Email (Data + Email option): Shows "XXXXXX@domain"
		- Date: Shows "XX-XX-XXXX"
		- Time: Shows "XX:XX"
		- Default: Shows "XXXXXXXX"
	"""
	if not val:
		return val

	if field.fieldtype == "Data" and field.options == "Phone":
		if len(val) > 3:
			return val[:3] + "XXXXXX"
		else:
			return "X" * len(val)
	elif field.fieldtype == "Data" and field.options == "Email":
		email = val.split("@")
		return "XXXXXX@" + email[1] if len(email) > 1 else "XXXXXX"
	elif field.fieldtype == "Date":
		return "XX-XX-XXXX"
	elif field.fieldtype == "Time":
		return "XX:XX"
	else:
		return "XXXXXXXX"


def mask_dict_results(result, masked_fields):
	"""Mask fields in dictionary results.

	Args:
		result: List of dictionaries containing query results
		masked_fields: List of DocField objects with masking configuration

	Returns:
		Result with masked field values
	"""
	for row in result:
		for field in masked_fields:
			if field.fieldname in row:
				row[field.fieldname] = mask_field_value(field, row[field.fieldname])
	return result


def mask_list_results(result, masked_fields, field_index_map):
	"""Mask fields in list/tuple results.

	Args:
		result: List of tuples containing query results
		masked_fields: List of DocField objects with masking configuration
		field_index_map: Dict mapping field names to their position in result tuples

	Returns:
		List of tuples with masked field values
	"""
	masked_result = []
	for row in result:
		row = list(row)  # Convert tuple to list for modification
		for field in masked_fields:
			if field.fieldname in field_index_map:
				idx = field_index_map[field.fieldname]
				row[idx] = mask_field_value(field, row[idx])
		masked_result.append(tuple(row))  # Convert back to tuple
	return masked_result
