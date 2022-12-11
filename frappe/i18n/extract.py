from typing import Any, Iterator, TextIO


def extract_doctype_json(
	fileobj: TextIO, keywords: list[str], comment_tags: list[str], options: dict[str, Any]
) -> Iterator[tuple[int, str, tuple[str | None, str], list[str]]]:
	"""Extract messages from DocType JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:param keywords: unused
	:param comment_tags: unused
	:param options: unused
	:return: an iterator over `(None, "pgettext", (context, message), [])` tuples
	:rtype: `iterator`
	"""
	from json import load

	# pretend to use `pgettext` as the function name. This way we can supply the doctype name as context
	FUNCNAME = "pgettext"

	data = load(fileobj)
	if isinstance(data, list):
		return

	doctype = data.get("name")
	yield None, FUNCNAME, (None, doctype), ["Name of a DocType"]

	for field in data.get("fields", []):
		fieldtype = field.get("fieldtype")
		if label := field.get("label"):
			yield None, FUNCNAME, (doctype, label), [f"Label of a {fieldtype} field in DocType '{doctype}'"]

		if description := field.get("description"):
			yield None, FUNCNAME, (doctype, description), [f"Description of a field in DocType '{doctype}'"]

		if message := field.get("options"):
			if fieldtype == "Select":
				select_options = [option for option in message.split("\n") if option and not option.isdigit()]
				if select_options and "icon" in select_options[0]:
					continue
				for option in select_options:
					yield None, FUNCNAME, (doctype, option), [
						f"Option for a {fieldtype} field in DocType '{doctype}'"
					]
			elif fieldtype == "HTML":
				yield None, FUNCNAME, (doctype, message), [
					f"Content of an {fieldtype} field in DocType '{doctype}'"
				]

	for perm in data.get("permissions", []):
		if role := perm.get("role"):
			# pass None as context because translation of the role should not depend on the doctype
			yield None, FUNCNAME, (None, role), ["Name of a role"]

	for link in data.get("links", []):
		if group := link.get("group"):
			yield None, FUNCNAME, (doctype, group), [f"Group in {doctype}'s connections"]

		if link_doctype := link.get("link_doctype"):
			yield None, FUNCNAME, (doctype, link_doctype), [f"Linked DocType in {doctype}'s connections"]


def extract_python(
	fileobj: TextIO, keywords: list[str], comment_tags: list[str], options: dict[str, Any]
) -> Iterator[tuple[int, str, tuple[str | None, str], list[str]]]:
	"""Extract messages from python files.

	:param fileobj: the file-like object the messages should be extracted from
	:param keywords: unused
	:param comment_tags: unused
	:param options: unused
	:return: an iterator over `(None, "pgettext", (context, message), [])` tuples
	:rtype: `iterator`
	"""
	from babel.messages.extract import extract_python

	# pretend to use `pgettext` as the function name. This way we can supply the doctype name as context
	FUNCNAME = "pgettext"

	for message in extract_python(
		fileobj,
		keywords=["_"],
		comment_tags=(),
		options={},
	):
		lineno, _func, args, _comments = message

		if not args or not args[0]:
			continue

		source_text = args[0] if isinstance(args, tuple) else args
		context = args[1] if len(args) == 2 else None

		yield lineno, FUNCNAME, (context, source_text), _comments
