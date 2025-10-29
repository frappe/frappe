import json

from .utils import EXCLUDE_SELECT_OPTIONS, extract_messages_from_docfield, extract_messages_from_links


def extract(fileobj, *args, **kwargs):
	"""Extract messages from `custom/{doctype}.json` files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	doctype = data.get("doctype")

	messages = []

	for field in data.get("custom_fields", []):
		messages.extend(extract_messages_from_docfield(doctype, field))

	messages.extend(extract_messages_from_links(doctype, data.get("links", [])))

	for property_setter in data.get("property_setters", []):
		if property_setter.get("doctype_or_field") != "DocField":
			continue

		property_name = property_setter.get("property")

		fieldname = property_setter.get("field_name")
		if property_name == "options" and fieldname not in EXCLUDE_SELECT_OPTIONS:
			message = property_setter.get("value")
			select_options = [option for option in message.split("\n") if option and not option.isdigit()]

			if select_options and "icon" in select_options[0]:
				continue

			messages.extend(
				(
					option,
					f"Option for the '{fieldname}' (Select) field in DocType '{doctype}'",
				)
				for option in select_options
			)

		if property_name == "label":
			messages.append(
				(
					property_setter.get("value"),
					f"Label of the '{fieldname}' field in DocType '{doctype}'",
				)
			)

		if property_name == "description":
			messages.append(
				(
					property_setter.get("value"),
					f"Description of the '{fieldname}' field in DocType '{doctype}'",
				)
			)

	yield from ((None, "_", message, [comment]) for message, comment in messages)
