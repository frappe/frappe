import json

EXCLUDE_SELECT_OPTIONS = [
	"naming_series",
	"number_format",
	"float_precision",
	"currency_precision",
	"minimum_password_score",
]


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	doctype = data.get("doctype")

	messages = []
	fields = data.get("custom_fields", [])

	for field in fields:
		fieldtype = field.get("fieldtype")
		fieldname = field.get("fieldname")
		label = field.get("label")

		if label:
			messages.append((label, f"Label of a {fieldtype} field in Customization of DocType '{doctype}'"))
			_label = label
		else:
			_label = fieldname

		if description := field.get("description"):
			messages.append(
				(
					description,
					f"Description of the '{_label}' ({fieldtype}) field in Customization of DocType '{doctype}'",
				)
			)

		if message := field.get("options"):
			if fieldtype == "Select":
				if fieldname in EXCLUDE_SELECT_OPTIONS:
					continue

				select_options = [option for option in message.split("\n") if option and not option.isdigit()]

				if select_options and "icon" in select_options[0]:
					continue

				messages.extend(
					(
						option,
						f"Option for the '{_label}' ({fieldtype}) field in Customization of DocType '{doctype}'",
					)
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append(
					(
						message,
						f"Content of the '{_label}' ({fieldtype}) field in Customization of DocType '{doctype}'",
					)
				)

	# By using "pgettext" as the function name we can supply the doctype as context
	yield from ((None, "pgettext", (doctype, message), [comment]) for message, comment in messages)
