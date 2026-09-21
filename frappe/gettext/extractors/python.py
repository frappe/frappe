import ast

from babel.messages.extract import extract_python


def extract(fileobj, *args, **kwargs):
	"""
	Wrapper around babel's `extract_python`, handling our own implementation of `_()`

	Babel flattens the arguments, so `_("msg", lang="de")` looks like `_("msg", context="ctx")`;
	two values only carry a context when the `context` keyword is used.
	"""
	try:
		calls = [node for node in ast.walk(ast.parse(fileobj.read())) if isinstance(node, ast.Call)]
	except SyntaxError:
		calls = []
	fileobj.seek(0)

	lines_with_context_keyword = {
		call.lineno
		for call in calls
		if (getattr(call.func, "id", None) or getattr(call.func, "attr", None)) in ("_", "_lt")
		and any(keyword.arg == "context" for keyword in call.keywords)
	}

	for lineno, funcname, messages, comments in extract_python(fileobj, *args, **kwargs):
		if (
			funcname in ("_", "_lt")
			and isinstance(messages, tuple)
			and (len(messages) > 2 or lineno in lines_with_context_keyword)
		):
			funcname = "pgettext"
			messages = (messages[-1], messages[0])  # (context, message)

		yield lineno, funcname, messages, comments
