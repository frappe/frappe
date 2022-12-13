def extract_doctype_json(fileobj, *args, **kwargs):
	"""Extract messages from DocType JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	from json import load

	data = load(fileobj)
	if isinstance(data, list):
		return

	doctype = data.get("name")
	yield None, "_", doctype, ["Name of a DocType"]

	messages = []
	for field in data.get("fields", []):
		fieldtype = field.get("fieldtype")
		if label := field.get("label"):
			messages.append((label, f"Label of a {fieldtype} field in DocType '{doctype}'"))

		if description := field.get("description"):
			messages.append((description, f"Description of a {fieldtype} field in DocType '{doctype}'"))

		if message := field.get("options"):
			if fieldtype == "Select":
				select_options = [option for option in message.split("\n") if option and not option.isdigit()]
				if select_options and "icon" in select_options[0]:
					continue
				messages.extend(
					(option, f"Option for a {fieldtype} field in DocType '{doctype}'")
					for option in select_options
				)
			elif fieldtype == "HTML":
				messages.append((message, f"Content of an {fieldtype} field in DocType '{doctype}'"))

	for link in data.get("links", []):
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


def extract_python(*args, **kwargs):
	"""Wrapper around babel's `extract_python`, handling our own implementation of `_()`"""
	from babel.messages.extract import extract_python

	for lineno, funcname, messages, comments in extract_python(*args, **kwargs):
		# handle our own implementation of `_()`
		if funcname == "_" and isinstance(messages, tuple) and len(messages) > 1:
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments
