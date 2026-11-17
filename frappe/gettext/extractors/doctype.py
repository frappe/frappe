import json

from .utils import get_line_number

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

	for field in fields:
		fieldtype = field.get("fieldtype")
		fieldname = field.get("fieldname")
		label = field.get("label")

		if label:
			messages.append(
				(
					get_line_number(text, "label", label),
					label,
					f"Label of a {fieldtype} field in DocType '{doctype}'",
				)
			)
			_label = label
		else:
			_label = fieldname

		if description := field.get("description"):
			messages.append(
				(
					get_line_number(text, "description", description),
					description,
					f"Description of the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
				)
			)

		if message := field.get("options"):
			lineno = get_line_number(text, "options", message)
			if fieldtype == "Select":
				if fieldname in EXCLUDE_SELECT_OPTIONS:
					continue

				select_options = [option for option in message.split("\n") if option and not option.isdigit()]

				if select_options and "icon" in select_options[0]:
					continue

				messages.extend(
					(
						lineno,
						option,
						f"Option for the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
					)
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append(
					(lineno, message, f"Content of the '{_label}' ({fieldtype}) field in DocType '{doctype}'")
				)

	for link in links:
		if group := link.get("group"):
			messages.append(
				(get_line_number(text, "group", group), group, f"Group in {doctype}'s connections")
			)

		if link_doctype := link.get("link_doctype"):
			messages.append(
				(
					get_line_number(text, "link_doctype", link_doctype),
					link_doctype,
					f"Linked DocType in {doctype}'s connections",
				)
			)

	# By using "pgettext" as the function name we can supply the doctype as context
	yield from ((lineno, "_", message, [comment]) for lineno, message, comment in messages)

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(get_line_number(text, "role", perm["role"]), "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)
