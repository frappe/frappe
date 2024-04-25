from jinja2.ext import babel_extract

from .utils import extract_messages_from_code


def extract(*args, **kwargs):
	"""Extract messages from Jinja and JS microtemplates.

	Reuse the babel_extract function from jinja2.ext, but handle our own implementation of `_()`.
	To handle JS microtemplates, parse all code again using regex."""
	fileobj = args[0] or kwargs["fileobj"]

	code = fileobj.read().decode("utf-8")

	for lineno, funcname, messages, comments in babel_extract(*args, **kwargs):
		if funcname == "_" and isinstance(messages, tuple) and len(messages) > 1:
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments

	for lineno, message, context in extract_messages_from_code(code):
		if context:
			yield lineno, "pgettext", (context, message), []
		else:
			yield lineno, "_", message, []
