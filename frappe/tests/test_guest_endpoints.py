import ast
import textwrap
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

ABOVE_WHITELIST = "@rate_limit is above @frappe.whitelist, so the endpoint is not whitelisted"
MISSING_METHODS = "guest endpoint must declare methods=[...]"
MISSING_RATE_LIMIT = "guest endpoint needs @rate_limit(...) below @frappe.whitelist, or rate_limit=None"
BOTH_RATE_LIMITS = "guest endpoint has both @rate_limit and rate_limit=None"
INVALID_RATE_LIMIT = "rate_limit only accepts None; use the @rate_limit(...) decorator"


def _name(decorator: ast.expr) -> str | None:
	if isinstance(decorator, ast.Call):
		decorator = decorator.func
	if isinstance(decorator, ast.Attribute):
		return decorator.attr
	if isinstance(decorator, ast.Name):
		return decorator.id
	return None


def _keyword(call: ast.Call, arg: str) -> ast.expr | None:
	return next((keyword.value for keyword in call.keywords if keyword.arg == arg), None)


def _is_empty(value: ast.expr) -> bool:
	if isinstance(value, ast.Constant):
		return not value.value
	if isinstance(value, ast.List | ast.Tuple):
		return not value.elts
	return False


def find_guest_endpoint_problems(source: str, filename: str = "<source>") -> list[str]:
	"""Return `file:line function: problem` for every whitelisted function that breaks the guest
	endpoint contract: declared HTTP methods, and either `@rate_limit` below `@frappe.whitelist`
	or `rate_limit=None`."""
	problems = []

	for node in ast.walk(ast.parse(source, filename)):
		if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
			continue

		names = [_name(decorator) for decorator in node.decorator_list]
		if "whitelist" not in names:
			continue

		position = names.index("whitelist")
		whitelist = node.decorator_list[position]

		def report(problem):
			problems.append(f"{filename}:{whitelist.lineno} {node.name}: {problem}")

		if "rate_limit" in names[:position]:
			report(ABOVE_WHITELIST)

		if not isinstance(whitelist, ast.Call):
			continue

		allow_guest = _keyword(whitelist, "allow_guest")
		if not (isinstance(allow_guest, ast.Constant) and allow_guest.value):
			continue

		methods = _keyword(whitelist, "methods")
		if methods is None or _is_empty(methods):
			report(MISSING_METHODS)

		exemption = _keyword(whitelist, "rate_limit")
		limited = "rate_limit" in names[position + 1 :]

		if exemption is None:
			if not limited:
				report(MISSING_RATE_LIMIT)
		elif not (isinstance(exemption, ast.Constant) and exemption.value is None):
			report(INVALID_RATE_LIMIT)
		elif limited:
			report(BOTH_RATE_LIMITS)

	return problems


class TestGuestEndpoints(UnitTestCase):
	def test_guest_endpoints_declare_methods_and_rate_limit(self):
		app_path = Path(frappe.get_app_path("frappe"))
		problems = []
		for path in sorted(app_path.rglob("*.py")):
			if "node_modules" in path.parts:
				continue
			source = path.read_text(encoding="utf-8")
			if "whitelist" not in source:
				continue
			problems.extend(find_guest_endpoint_problems(source, str(path.relative_to(app_path.parent))))

		self.assertEqual(problems, [], "\n" + "\n".join(problems))

	def test_checker_reports_each_problem(self):
		def problems(source):
			return [
				problem.split(": ", 1)[1] for problem in find_guest_endpoint_problems(textwrap.dedent(source))
			]

		self.assertEqual(
			problems(
				"""
				@frappe.whitelist(allow_guest=True)
				def bare(): ...
				"""
			),
			[MISSING_METHODS, MISSING_RATE_LIMIT],
		)
		self.assertEqual(
			problems(
				"""
				@frappe.whitelist(allow_guest=True, methods=[])
				@rate_limit(limit=5, seconds=60)
				def empty_methods(): ...
				"""
			),
			[MISSING_METHODS],
		)
		self.assertEqual(
			problems(
				"""
				@rate_limit(limit=5, seconds=60)
				@frappe.whitelist(allow_guest=True, methods=["POST"])
				def reversed_order(): ...
				"""
			),
			[ABOVE_WHITELIST, MISSING_RATE_LIMIT],
		)
		self.assertEqual(
			problems(
				"""
				@rate_limit(limit=5, seconds=60)
				@frappe.whitelist()
				def reversed_order_logged_in(): ...
				"""
			),
			[ABOVE_WHITELIST],
		)
		self.assertEqual(
			problems(
				"""
				@frappe.whitelist(allow_guest=True, methods=["GET"], rate_limit=None)
				@rate_limit(limit=5, seconds=60)
				def both(): ...
				"""
			),
			[BOTH_RATE_LIMITS],
		)
		self.assertEqual(
			problems(
				"""
				@frappe.whitelist(allow_guest=True, methods=["GET"], rate_limit=10)
				def invalid(): ...
				"""
			),
			[INVALID_RATE_LIMIT],
		)

	def test_checker_accepts_declared_endpoints(self):
		source = textwrap.dedent(
			"""
			@frappe.whitelist(allow_guest=True, methods=["POST"])
			@rate_limit(limit=5, seconds=60)
			def limited(): ...

			@frappe.whitelist(allow_guest=True, methods=["GET"], rate_limit=None)
			def exempt(): ...

			@frappe.whitelist()
			def logged_in(): ...
			"""
		)
		self.assertEqual(find_guest_endpoint_problems(source), [])

	def test_whitelist_rate_limit_only_accepts_none(self):
		def exempt():
			pass

		exempt = frappe.whitelist(allow_guest=True, methods=["GET"], rate_limit=None)(exempt)
		self.assertIn(exempt, frappe.guest_methods)

		with self.assertRaises(TypeError):
			frappe.whitelist(allow_guest=True, methods=["GET"], rate_limit=10)
