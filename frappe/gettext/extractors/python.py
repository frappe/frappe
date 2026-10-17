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
<<<<<<< HEAD
=======


def _func_name(call):
	return getattr(call.func, "id", None) or getattr(call.func, "attr", None)


def _constant(node):
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def _context(call):
	"""Context is the third positional argument or the `context` keyword of `_()`."""
	for keyword in call.keywords:
		if keyword.arg == "context":
			return _constant(keyword.value)
	if len(call.args) > 2:
		return _constant(call.args[2])
	return None


def _translation_calls(source):
	"""Map line numbers to the `_()` / `_lt()` calls whose message is on them, in source order."""
	by_line = {}
	try:
		nodes = ast.walk(ast.parse(source))
	except SyntaxError:
		return by_line

	for node in nodes:
		if isinstance(node, ast.Call) and _func_name(node) in ("_", "_lt"):
			message_line = node.args[0].lineno if node.args else node.lineno
			by_line.setdefault(message_line, []).append(node)

	for calls in by_line.values():
		calls.sort(key=lambda call: call.col_offset)
	return by_line


def _take_call(calls_by_line, lineno, msgid):
	"""Pop the call babel just reported, so several calls on one line stay apart."""
	calls = calls_by_line.get(lineno)
	if not calls:
		return None
	for i, call in enumerate(calls):
		if call.args and _constant(call.args[0]) == msgid:
			return calls.pop(i)
	return calls.pop(0)
>>>>>>> 09207e2 (chore(deps): bump babel to 2.18.0 (#44596))
