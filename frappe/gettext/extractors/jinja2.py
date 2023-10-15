from jinja2.ext import babel_extract


def extract(*args, **kwargs):
	"""Reuse the babel_extract function from jinja2.ext, but handle our own implementation of `_()`"""
	for lineno, funcname, messages, comments in babel_extract(*args, **kwargs):
		if funcname == "_" and isinstance(messages, tuple) and len(messages) > 1:
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments
