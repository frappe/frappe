import ast

from babel.messages.extract import extract_python


def extract(fileobj, *args, **kwargs):
	"""
	Wrapper around babel's `extract_python`, handling our own implementation of `_()`

	Babel flattens the arguments, so `_("msg", lang="de")` looks like `_("msg", context="ctx")`.
	To tell them apart we parse the file ourselves and read the context off the AST.
	"""
	calls_by_line = _translation_calls(fileobj.read())
	fileobj.seek(0)

	for lineno, funcname, messages, comments in extract_python(fileobj, *args, **kwargs):
		if funcname in ("_", "_lt"):
			msgid = messages[0] if isinstance(messages, tuple) else messages
			call = _take_call(calls_by_line, lineno, msgid)
			context = _context(call) if call else None
			if context and msgid:
				funcname = "pgettext"
				messages = (context, msgid)

		yield lineno, funcname, messages, comments


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
	"""Map line numbers to the `_()` / `_lt()` calls starting on them, in source order."""
	by_line = {}
	try:
		nodes = ast.walk(ast.parse(source))
	except SyntaxError:
		return by_line

	for node in nodes:
		if isinstance(node, ast.Call) and _func_name(node) in ("_", "_lt"):
			by_line.setdefault(node.lineno, []).append(node)

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
