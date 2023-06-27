import frappe
from frappe.utils.safe_exec import safe_exec


def safe_block_eval(script: str, _globals=None, _locals=None, output_var=None, **kwargs):
	"""Evaluate a block of code and return the result.

	Allows `return` statements and `yield` expressions in the code to make it easier to write code that should return a value.

	Args:
	        script (str): The code to evaluate. Will be wrapped in a function.
	        _globals (dict, optional): Globals
	        _locals (dict, optional): Locals
	        output_var (str, optional): The name of the variable to store the result in. Randomly generated if not provided.
	        restrict_commit_rollback (bool, optional)

	Returns:
	        any: The result of the evaluation of the code.
	"""

	output_var = output_var or "evaluated_code_output_" + frappe.generate_hash(length=5)
	_locals = _locals or {}
	script = _wrap_in_function(script, output_var=output_var, local_vars=_locals)
	safe_exec(script, _globals, _locals, **kwargs)
	return _locals[output_var]


def _wrap_in_function(
	code: str,
	*,
	output_var: str = "evaluated_code_output_var_",
	local_vars: dict[str, None] | None = None,
	function_name: str = "evaluated_code_wrapper_function_",
) -> str:
	"""Wrap code in a function so that it can contain `return` statements."""
	import textwrap

	# Convert newlines to \n and remove leading/trailing newlines
	code = (
		code.replace("\r\n", "\n")
		.replace("\r", "")
		.replace("\u2028", "\n")
		.replace("\u2029", "\n")
		.strip("\n")
	)

	# If code is a single line, and does not contain a return statement, then prepend one
	if "\n" not in code and " = " not in code:
		start_keywords = {"return ", "raise ", "assert ", "yield "}
		if not any(code.startswith(keyword) for keyword in start_keywords):
			code = f"return {code}"

	# Detect the indentation to avoid mixing tabs and spaces.
	# Any amount of leading spaces is accepted as long as it is consistent.
	indent = "\t" if "\t" in code else "    "

	# Indent the code
	code = textwrap.indent(code, indent)

	args = ", ".join(
		key
		for key in (local_vars or {}).keys()
		if key != output_var and not key.startswith("_") and key.isidentifier()
	)
	code = f"def {function_name}({args}):\n{code}\n\n{output_var} = {function_name}({args})"
	return code


def validate(code_string: str, fieldname: str):
	"""Validate a block of code by first wrapping it in a function and then compiling it."""
	from frappe.utils import validate_python_code

	code_string = _wrap_in_function(code_string)
	return validate_python_code(code_string, fieldname=fieldname, is_expression=False)
