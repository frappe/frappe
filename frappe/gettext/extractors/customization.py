import json

from .utils import (
	EXCLUDE_SELECT_OPTIONS,
	extract_messages_from_docfield,
	extract_messages_from_links,
	get_line_number,
)


def extract(fileobj, *args, **kwargs):
	"""Extract messages from `custom/{doctype}.json` files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	doctype = data.get("doctype")

	messages = []

	for field in data.get("custom_fields", []):
		messages.extend(extract_messages_from_docfield(doctype, field, text))

	messages.extend(extract_messages_from_links(doctype, data.get("links", []), text))

	for property_setter in data.get("property_setters", []):
		if property_setter.get("doctype_or_field") != "DocField":
			continue

		property_name = property_setter.get("property")

		fieldname = property_setter.get("field_name")
		value = property_setter.get("value")
		lineno = get_line_number(text, "value", value)
		if property_name == "options" and fieldname not in EXCLUDE_SELECT_OPTIONS:
			select_options = [option for option in value.split("\n") if option and not option.isdigit()]

			if select_options and "icon" in select_options[0]:
				continue

			messages.extend(
				(
					lineno,
					option,
					f"Option for the '{fieldname}' (Select) field in DocType '{doctype}'",
				)
				for option in select_options
			)

		if property_name == "label":
			messages.append(
				(
					lineno,
					value,
					f"Label of the '{fieldname}' field in DocType '{doctype}'",
				)
			)

		if property_name == "description":
			messages.append(
				(
					lineno,
					value,
					f"Description of the '{fieldname}' field in DocType '{doctype}'",
				)
			)

	yield from ((lineno, "_", message, [comment]) for lineno, message, comment in messages)
