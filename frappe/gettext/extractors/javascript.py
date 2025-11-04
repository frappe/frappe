from io import BufferedReader


def extract(fileobj: BufferedReader, keywords: str, comment_tags: tuple, options: dict):
	code = fileobj.read().decode("utf-8")

	for lineno, funcname, messages in extract_javascript(code, options=options):
		if not messages or not messages[0]:
			continue

		# `funcname` here will be `__` which is our translation function. We
		# have to convert it back to usual function names
		funcname = "gettext"

		if isinstance(messages, tuple):
			if len(messages) == 3 and messages[2]:
				funcname = "pgettext"
				messages = (messages[2], messages[0])
			else:
				messages = messages[0]

		yield lineno, funcname, messages, []


def extract_javascript(code, keywords=None, options=None, lineno=1):
	"""Extract messages from JavaScript source code.

	This is a modified version of babel's JS parser. Reused under BSD license.
	License: https://github.com/python-babel/babel/blob/master/LICENSE

	Changes from upstream:
	- Preserve arguments, babel's parser flattened all values in args,
	  we need order because we use different syntax for translation
	  which can contain 2nd arg which is array of many values. If
	  argument is non-primitive type then value is NOT returned in
	  args.
	  E.g. __("0", ["1", "2"], "3") -> ("0", None, "3")
	- remove comments support
	- changed signature to accept string directly.

	:param code: code as string
	:param keywords: a list of keywords (i.e. function names) that should be recognized as translation functions
	    Defaults to ("__",)
	:param options: a dictionary of additional options (optional)
	    Supported options are:
	        * `template_string` -- set to false to disable ES6 template string support.
	"""
	from babel.messages.jslexer import Token, tokenize, unquote_string

	if options is None:
		options = {}

	if keywords is None:
		keywords = ("__",)

	funcname = message_lineno = None
	messages = []
	last_argument = None
	concatenate_next = False
	last_token = None
	call_stack = -1

	# Tree level = depth inside function call tree
	#  Example: __("0", ["1", "2"], "3")
	# Depth         __()
	#             /   |   \
	#   0       "0" [...] "3"  <- only 0th level strings matter
	#                /  \
	#   1          "1"  "2"
	tree_level = 0
	opening_operators = {"[", "{"}
	closing_operators = {"]", "}"}
	all_container_operators = opening_operators.union(closing_operators)
	dotted = any("." in kw for kw in keywords)

	for token in tokenize(
		code,
		jsx=True,
		dotted=dotted,
		template_string=options.get("template_string", True),
		lineno=lineno,
	):
		if (  # Turn keyword`foo` expressions into keyword("foo") calls:
			funcname
			and (last_token and last_token.type == "name")  # have a keyword...
			and token.type  # we've seen nothing after the keyword...
			== "template_string"  # this is a template string
		):
			message_lineno = token.lineno
			messages = [unquote_string(token.value)]
			call_stack = 0
			tree_level = 0
			token = Token("operator", ")", token.lineno)

		if not funcname and token.type == "template_string":
			yield from parse_template_string(token.value, keywords, options, token.lineno)

		if token.type == "operator" and token.value == "(":
			if funcname:
				message_lineno = token.lineno
				call_stack += 1

		elif call_stack >= 0 and token.type == "operator" and token.value in all_container_operators:
			if token.value in opening_operators:
				tree_level += 1
			if token.value in closing_operators:
				tree_level -= 1

		elif (call_stack == -1 and token.type == "linecomment") or token.type == "multilinecomment":
			pass  # ignore comments

		elif funcname and call_stack == 0:
			if token.type == "operator" and token.value == ")":
				if last_argument is not None:
					messages.append(last_argument)
				if len(messages) > 1:
					messages = tuple(messages)
				elif messages:
					messages = messages[0]
				else:
					messages = None

				if messages is not None:
					yield (message_lineno, funcname, messages)

				funcname = message_lineno = last_argument = None
				concatenate_next = False
				messages = []
				call_stack = -1
				tree_level = 0

			elif token.type in ("string", "template_string"):
				new_value = unquote_string(token.value)
				if tree_level > 0:
					pass
				elif concatenate_next:
					last_argument = (last_argument or "") + new_value
					concatenate_next = False
				else:
					last_argument = new_value

			elif token.type == "operator":
				if token.value == ",":
					if last_argument is not None:
						messages.append(last_argument)
						last_argument = None
					else:
						if tree_level == 0:
							messages.append(None)
					concatenate_next = False
				elif token.value == "+":
					concatenate_next = True

		elif call_stack > 0 and token.type == "operator" and token.value == ")":
			call_stack -= 1
			tree_level = 0

		elif funcname and call_stack == -1:
			funcname = None

		elif (
			call_stack == -1
			and token.type == "name"
			and token.value in keywords
			and (last_token is None or last_token.type != "name" or last_token.value != "function")
		):
			funcname = token.value

		last_token = token


def parse_template_string(
	template_string,
	keywords,
	options,
	lineno=1,
):
	"""Parse JavaScript template string.

	This is a modified version of babel's JS parser. Reused under BSD license.
	License: https://github.com/python-babel/babel/blob/master/LICENSE

	:param template_string: the template string to be parsed
	:param keywords: a list of keywords (i.e. function names) that should be recognized as translation functions
	:param options: a dictionary of additional options (optional)
	:param lineno: starting line number (optional)
	"""
	from babel.messages.jslexer import line_re

	prev_character = None
	level = 0
	inside_str = False
	expression_contents = ""
	for character in template_string[1:-1]:
		if not inside_str and character in ('"', "'", "`"):
			inside_str = character
		elif inside_str == character and prev_character != r"\\":
			inside_str = False
		if level:
			expression_contents += character
		if not inside_str:
			if character == "{" and prev_character == "$":
				level += 1
			elif level and character == "}":
				level -= 1
				if level == 0 and expression_contents:
					expression_contents = expression_contents[:-1]
					yield from extract_javascript(expression_contents, keywords, options, lineno)
					lineno += len(line_re.findall(expression_contents))
					expression_contents = ""
		prev_character = character
