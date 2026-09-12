import ast

from babel.messages.extract import extract_python


def extract(fileobj, *args, **kwargs):
	"""
	Wrapper around babel's `extract_python`, handling our own implementation of `_()`.

	`_(msg, lang, context)` accepts an optional ``lang`` before ``context``. Babel only sees
	the flattened argument values, so it cannot tell ``lang`` from ``context`` and would tag
	``_("msg", lang="de")`` with ``de`` as context. The context is read from the AST instead.
	"""
	code = fileobj.read()
	fileobj.seek(0)

	contexts = _translation_contexts(code)

	for lineno, funcname, messages, comments in extract_python(fileobj, *args, **kwargs):
		if funcname in ("_", "_lt"):
			message = messages[0] if isinstance(messages, tuple) else messages
			context = contexts.get((lineno, message))
			if context:
				funcname = "pgettext"
				messages = (context, message)
			else:
				messages = message

		yield lineno, funcname, messages, comments


def _translation_contexts(code: str) -> dict[tuple[int, str], str]:
	"""Map ``(lineno, message)`` to the context passed to ``_()``/``_lt()`` in the code."""
	contexts = {}

	try:
		tree = ast.parse(code)
	except SyntaxError:
		return contexts

	for node in ast.walk(tree):
		if not isinstance(node, ast.Call):
			continue

		func = node.func
		name = (
			func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
		)
		if name not in ("_", "_lt") or not node.args:
			continue

		message = _string_literal(node.args[0])
		if not message:
			continue

		context = _string_literal(node.args[2]) if len(node.args) >= 3 else None
		for keyword in node.keywords:
			if keyword.arg == "context":
				context = _string_literal(keyword.value)

		if context:
			contexts[(node.lineno, message)] = context

	return contexts


def _string_literal(node: ast.expr) -> str | None:
	"""Return the string literal of a node, unwrapping ``"literal".method(...)`` calls."""
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
		return _string_literal(node.func.value)
	return None
