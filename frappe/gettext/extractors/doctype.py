import json

<<<<<<< HEAD
EXCLUDE_SELECT_OPTIONS = [
	"naming_series",
	"number_format",
	"float_precision",
	"currency_precision",
	"minimum_password_score",
]
=======
from .utils import extract_messages_from_docfield, extract_messages_from_links, get_line_number
>>>>>>> 6c919fb (feat(gettext): add line numbers for strings from JSON files (#44603))


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	doctype = data.get("name")

	yield get_line_number(text, "name", doctype), "_", doctype, ["Name of a DocType"]

	doctype_description = data.get("description")
	if doctype_description:
		yield (
			get_line_number(text, "description", doctype_description),
			"_",
			doctype_description,
			["Description of a DocType"],
		)

	messages = []
	fields = data.get("fields", [])
	links = data.get("links", [])

<<<<<<< HEAD
	for field in fields:
		fieldtype = field.get("fieldtype")
		fieldname = field.get("fieldname")
		label = field.get("label")

		if label:
			messages.append((label, f"Label of a {fieldtype} field in DocType '{doctype}'"))
			_label = label
		else:
			_label = fieldname

		if description := field.get("description"):
			messages.append(
				(description, f"Description of the '{_label}' ({fieldtype}) field in DocType '{doctype}'")
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
						f"Option for the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
					)
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append(
					(message, f"Content of the '{_label}' ({fieldtype}) field in DocType '{doctype}'")
				)

	for link in links:
		if group := link.get("group"):
			messages.append((group, f"Group in {doctype}'s connections"))

		if link_doctype := link.get("link_doctype"):
			messages.append((link_doctype, f"Linked DocType in {doctype}'s connections"))

	# By using "pgettext" as the function name we can supply the doctype as context
	yield from ((None, "_", message, [comment]) for message, comment in messages)
=======
	for field in data.get("fields", []):
		messages.extend(extract_messages_from_docfield(doctype, field, text))

	messages.extend(extract_messages_from_links(doctype, data.get("links", []), text))

	yield from ((lineno, "_", message, [comment]) for lineno, message, comment in messages)
>>>>>>> 6c919fb (feat(gettext): add line numbers for strings from JSON files (#44603))

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(get_line_number(text, "role", perm["role"]), "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)
