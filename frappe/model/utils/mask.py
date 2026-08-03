# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import copy
from typing import Any


def as_aliased_field(df, alias: str | None):
	"""Return the docfield keyed by the alias it is selected under, since masking matches
	the result columns by fieldname (`items.rate as 'Item:rate'` lands under `Item:rate`)."""
	if not alias:
		return df

	df = copy.copy(df)
	df.fieldname = alias
	return df


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
		- Datetime: Shows "XX-XX-XXXX XX:XX"
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
	elif field.fieldtype == "Datetime":
		return "XX-XX-XXXX XX:XX"
	else:
		return "XXXXXXXX"


def mask_pluck_results(
	result: list[Any],
	masked_fields: list[Any],
	fields: list[Any],
) -> list[Any]:
	"""Mask plucked (scalar) results.

	With ``pluck``, the database layer has already reduced each row to the
	scalar value of the first selected field, so ``result`` is a flat list of
	values rather than a list of tuples/dicts. Mask each value when the
	plucked expression references a masked field — directly, or transitively
	through a wrapper (Coalesce, Max, aliased expressions, arithmetic, ...).

	Args:
		result: Flat list of scalar values (one per row)
		masked_fields: List of DocField objects with masking configuration
		fields: List of field objects from the query (the plucked field is first)

	Returns:
		List of scalar values, with the plucked value masked when the
		plucked expression references any masked field.
	"""
	if not fields:
		return result

	masked_names = {f.fieldname for f in masked_fields}

	# pypika's Term.fields_() returns every Field reference in the expression
	# subtree, so Coalesce(secret, x) / Max(secret) / secret + suffix all
	# surface the underlying "secret" reference. Non-Term items (raw string
	# fieldnames) don't have fields_(); fall back to a shallow name check.
	first = fields[0]
	alias = getattr(first, "alias", None)

	if alias and alias in masked_names:
		hit_name = alias
	elif hasattr(first, "fields_"):
		hit_name = next((f.name for f in first.fields_() if f.name in masked_names), None)
	else:
		# child / link fields selected through dot notation carry `fieldname`, not `name`
		name = getattr(first, "name", None) or getattr(first, "fieldname", None)
		hit_name = name if name in masked_names else None

	if not hit_name:
		return result

	masked_field = next(f for f in masked_fields if f.fieldname == hit_name)
	return [mask_field_value(masked_field, val) for val in result]


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
