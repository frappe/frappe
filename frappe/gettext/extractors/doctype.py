import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	doctype = data.get("name")

	yield None, "_", doctype, ["Name of a DocType"]

	doctype_description = data.get("description")
	if doctype_description:
		yield None, "_", doctype_description, ["Description of a DocType"]

	messages = []
	fields = data.get("fields", [])
	links = data.get("links", [])

	for field in fields:
		fieldtype = field.get("fieldtype")
		label = field.get("label")

		if label:
			messages.append((label, f"Label of a {fieldtype} field in DocType '{doctype}'"))
			_label = label
		else:
			_label = field.get("fieldname")

		if description := field.get("description"):
			messages.append(
				(description, f"Description of the '{_label}' ({fieldtype}) field in DocType '{doctype}'")
			)

		if message := field.get("options"):
			if fieldtype == "Select":
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
	yield from ((None, "pgettext", (doctype, message), [comment]) for message, comment in messages)

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(None, "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)
