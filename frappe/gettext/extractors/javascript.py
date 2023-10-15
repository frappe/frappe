from babel.messages.extract import extract_javascript


def extract(fileobj, keywords, comment_tags, options):
	# We use `__` as our translation function
	keywords = "__"

	for lineno, funcname, messages, comments in extract_javascript(
		fileobj, keywords, comment_tags, options
	):
		# `funcname` here will be `__` which is our translation function. We
		# have to convert it back to usual function names
		funcname = "gettext"

		if isinstance(messages, tuple):
			if len(messages) == 3:
				funcname = "pgettext"
				messages = (messages[2], messages[0])
			else:
				messages = messages[0]

		# ignore empty messages like `__(myvar)``
		if not messages:
			continue

		yield lineno, funcname, messages, comments
