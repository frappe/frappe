import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Web Form JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Web Form":
		return

	web_form_name = data.get("name")

	# Extract main web form fields
	if title := data.get("title"):
		yield None, "_", title, [f"Title of the {web_form_name} Web Form"]

	if introduction_text := data.get("introduction_text"):
		yield None, "_", introduction_text, [f"Introduction text of the {web_form_name} Web Form"]

	if success_message := data.get("success_message"):
		yield None, "_", success_message, [f"Success message of the {web_form_name} Web Form"]

	if success_title := data.get("success_title"):
		yield None, "_", success_title, [f"Success title of the {web_form_name} Web Form"]

	if list_title := data.get("list_title"):
		yield None, "_", list_title, [f"List title of the {web_form_name} Web Form"]

	if button_label := data.get("button_label"):
		yield None, "_", button_label, [f"Button label of the {web_form_name} Web Form"]

	if meta_title := data.get("meta_title"):
		yield None, "_", meta_title, [f"Meta title of the {web_form_name} Web Form"]

	if meta_description := data.get("meta_description"):
		yield None, "_", meta_description, [f"Meta description of the {web_form_name} Web Form"]

	# Extract web form fields
	for field in data.get("web_form_fields", []):
		if label := field.get("label"):
			yield None, "_", label, [f"Label of a field in the {web_form_name} Web Form"]

		if description := field.get("description"):
			yield None, "_", description, [f"Description of a field in the {web_form_name} Web Form"]

		# Extract options for Select fields
		if field.get("fieldtype") == "Select" and (options := field.get("options")):
			# Options can be either a newline-separated string or a reference to another DocType
			# Only extract if it's a string with newlines (indicating static options)
			if isinstance(options, str) and "\n" in options:
				for option in options.split("\n"):
					if option.strip():
						yield (
							None,
							"_",
							option.strip(),
							[f"Option in a Select field in the {web_form_name} Web Form"],
						)

	# Extract list columns
	for column in data.get("list_columns", []):
		if isinstance(column, dict) and (label := column.get("label")):
			yield None, "_", label, [f"Label of a list column in the {web_form_name} Web Form"]
