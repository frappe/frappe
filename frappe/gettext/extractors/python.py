from babel.messages.extract import extract_python


def extract(*args, **kwargs):
	"""
	Wrapper around babel's `extract_python`, handling our own implementation of `_()`
	"""
	for lineno, funcname, messages, comments in extract_python(*args, **kwargs):
		if funcname == "_" and isinstance(messages, tuple) and len(messages) > 1:
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments
