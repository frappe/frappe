import re

import frappe

TRANSLATE_PATTERN = re.compile(
	r"_\(\s*"  # starts with literal `_(`, ignore following whitespace/newlines
	# BEGIN: message search
	r"([\"']{,3})"  # start of message string identifier - allows: ', ", """, '''; 1st capture group
	r"(?P<message>((?!\1).)*)"  # Keep matching until string closing identifier is met which is same as 1st capture group
	r"\1"  # match exact string closing identifier
	# END: message search
	# BEGIN: python context search
	r"(\s*,\s*context\s*=\s*"  # capture `context=` with ignoring whitespace
	r"([\"'])"  # start of context string identifier; 5th capture group
	r"(?P<py_context>((?!\5).)*)"  # capture context string till closing id is found
	r"\5"  # match context string closure
	r")?"  # match 0 or 1 context strings
	# END: python context search
	# BEGIN: JS context search
	r"(\s*,\s*(.)*?\s*(,\s*"  # skip message format replacements: ["format", ...] | null | []
	r"([\"'])"  # start of context string; 11th capture group
	r"(?P<js_context>((?!\11).)*)"  # capture context string till closing id is found
	r"\11"  # match context string closure
	r")*"
	r")*"  # match one or more context string
	# END: JS context search
	r"\s*\)"  # Closing function call ignore leading whitespace/newlines
)

EXCLUDE_SELECT_OPTIONS = [
	"naming_series",
	"number_format",
	"float_precision",
	"currency_precision",
	"minimum_password_score",
	"icon",
]


def extract_messages_from_code(code):
	"""
	Extracts translatable strings from a code file
	:param code: code from which translatable files are to be extracted
	"""
	from jinja2 import TemplateError

	from frappe.model.utils import InvalidIncludePath, render_include

	try:
		code = frappe.as_unicode(render_include(code))

	# Exception will occur when it encounters John Resig's microtemplating code
	except (TemplateError, ImportError, InvalidIncludePath, OSError) as e:
		if isinstance(e, InvalidIncludePath) and hasattr(frappe.local, "message_log"):
			frappe.clear_last_message()
	except RuntimeError:
		# code depends on locals
		pass

	messages = []

	for m in TRANSLATE_PATTERN.finditer(code):
		message = m.group("message")
		context = m.group("py_context") or m.group("js_context")
		pos = m.start()

		if is_translatable(message):
			messages.append([pos, message, context])

	return add_line_number(messages, code)


def is_translatable(m):
	return bool(
		re.search("[a-zA-Z]", m)
		and not m.startswith("fa fa-")
		and not m.endswith("px")
		and not m.startswith("eval:")
	)


def add_line_number(messages, code):
	ret = []
	messages = sorted(messages, key=lambda x: x[0])
	newlines = [m.start() for m in re.compile(r"\n").finditer(code)]
	line = 1
	newline_i = 0
	for pos, message, context in messages:
		while newline_i < len(newlines) and pos > newlines[newline_i]:
			line += 1
			newline_i += 1
		ret.append([line, message, context])
	return ret


def extract_messages_from_docfield(doctype: str, field: dict):
	"""Extract translatable strings from docfield definition.

	`field` should have the following keys:

	- fieldtype: str
	- fieldname: str
	- label: str (optional)
	- description: str (optional)
	- options: str (optional)
	"""
	fieldtype = field.get("fieldtype")
	fieldname = field.get("fieldname")
	label = field.get("label")

	if label:
		yield label, f"Label of the {fieldname} ({fieldtype}) field in DocType '{doctype}'"
		_label = label
	else:
		_label = fieldname

	if description := field.get("description"):
		yield description, f"Description of the '{_label}' ({fieldtype}) field in DocType '{doctype}'"

	if message := field.get("options"):
		if fieldtype == "Select" and fieldname not in EXCLUDE_SELECT_OPTIONS:
			select_options = [option for option in message.split("\n") if option and not option.isdigit()]

			yield from (
				(
					option,
					f"Option for the '{_label}' ({fieldtype}) field in DocType '{doctype}'",
				)
				for option in select_options
			)
		elif fieldtype == "HTML":
			yield message, f"Content of the '{_label}' ({fieldtype}) field in DocType '{doctype}'"


def extract_messages_from_links(doctype: str, links: list[dict]):
	"""Extract translatable strings from a list of link definitions."""
	for link in links:
		if group := link.get("group"):
			yield group, f"Group in {doctype}'s connections"
