import json

from .utils import EXCLUDE_SELECT_OPTIONS


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Custom Field fixtures. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if not isinstance(data, list):
		return

	messages = []

	for custom_field in data:
		print(custom_field)
		fieldtype = custom_field.get("fieldtype")
		fieldname = custom_field.get("fieldname")
		label = custom_field.get("label")
		doctype = custom_field.get("dt")

		if label:
			messages.append((label, f"Label of the '{fieldname}' ({fieldtype}) field in DocType '{doctype}'"))
			_label = label
		else:
			_label = fieldname

		if description := custom_field.get("description"):
			messages.append(
				(
					description,
					f"Description of the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
				)
			)

		if message := custom_field.get("options"):
			if fieldtype == "Select":
				if fieldname in EXCLUDE_SELECT_OPTIONS:
					continue

				select_options = [option for option in message.split("\n") if option and not option.isdigit()]

				if select_options and "icon" in select_options[0]:
					continue

				messages.extend(
					(
						option,
						f"Option for the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
					)
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append(
					(message, f"Content of the '{_label}' ({fieldtype}) field in DocType '{doctype}'")
				)

	yield from ((None, "_", message, [comment]) for message, comment in messages)
