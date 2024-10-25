import types

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.safe_exec import ServerScriptNotEnabled, get_safe_globals, safe_exec


class TestSafeExec(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def test_import_fails(self) -> None:
		self.assertRaises(ImportError, safe_exec, "import os")

	def test_internal_attributes(self) -> None:
		self.assertRaises(SyntaxError, safe_exec, "().__class__.__call__")

	def test_utils(self) -> None:
		_locals = dict(out=None)
		safe_exec("""out = frappe.utils.cint("1")""", None, _locals)
		self.assertEqual(_locals["out"], 1)

	def test_safe_eval(self) -> None:
		TEST_CASES = {
			"1+1": 2,
			'"abc" in "abl"': False,
			'"a" in "abl"': True,
			'"a" in ("a", "b")': True,
			'"a" in {"a", "b"}': True,
			'"a" in {"a": 1, "b": 2}': True,
			'"a" in ["a" ,"b"]': True,
		}

		for code, result in TEST_CASES.items():
			self.assertEqual(frappe.safe_eval(code), result)

		self.assertRaises(AttributeError, frappe.safe_eval, "frappe.utils.os.path", get_safe_globals())

		# Doc/dict objects
		user = frappe.new_doc("User")
		user.user_type = "System User"
		user.enabled = 1
		self.assertTrue(frappe.safe_eval("user_type == 'System User'", eval_locals=user.as_dict()))
		self.assertEqual(
			"System User Test", frappe.safe_eval("user_type + ' Test'", eval_locals=user.as_dict())
		)
		self.assertEqual(1, frappe.safe_eval("int(enabled)", eval_locals=user.as_dict()))

	def test_safe_eval_wal(self) -> None:
		self.assertRaises(SyntaxError, frappe.safe_eval, "(x := (40+2))")

	def test_sql(self) -> None:
		_locals = dict(out=None)
		safe_exec(
			"""out = frappe.db.sql("select name from tabDocType where name='DocType'")""", None, _locals
		)
		self.assertEqual(_locals["out"][0][0], "DocType")

		self.assertRaises(
			frappe.PermissionError, safe_exec, 'frappe.db.sql("update tabToDo set description=NULL")'
		)

	def test_query_builder(self) -> None:
		_locals = dict(out=None)
		safe_exec(
			script="""out = frappe.qb.from_("User").select(frappe.qb.terms.PseudoColumn("Max(name)")).run()""",
			_globals=None,
			_locals=_locals,
		)
		self.assertEqual(frappe.db.sql("SELECT Max(name) FROM tabUser"), _locals["out"])

	def test_safe_query_builder(self) -> None:
		self.assertRaises(frappe.PermissionError, safe_exec, """frappe.qb.from_("User").delete().run()""")

	def test_call(self) -> None:
		# call non whitelisted method
		self.assertRaises(frappe.PermissionError, safe_exec, """frappe.call("frappe.get_user")""")

		# call whitelisted method
		safe_exec("""frappe.call("ping")""")

	def test_enqueue(self) -> None:
		# enqueue non whitelisted method
		self.assertRaises(
			frappe.PermissionError, safe_exec, """frappe.enqueue("frappe.get_user", now=True)"""
		)

		# enqueue whitelisted method
		safe_exec("""frappe.enqueue("ping", now=True)""")

	def test_ensure_getattrable_globals(self) -> None:
		def check_safe(objects) -> None:
			for obj in objects:
				if isinstance(obj, types.ModuleType | types.CodeType | types.TracebackType | types.FrameType):
					self.fail(f"{obj} wont work in safe exec.")
				elif isinstance(obj, dict):
					check_safe(obj.values())

		check_safe(get_safe_globals().values())

	def test_unsafe_objects(self) -> None:
		unsafe_global = {"frappe": frappe}
		self.assertRaises(SyntaxError, safe_exec, """frappe.msgprint("Hello")""", unsafe_global)

	def test_attrdict(self) -> None:
		# jinja
		frappe.render_template("{% set my_dict = _dict() %} {{- my_dict.works -}}")

		# RestrictedPython
		safe_exec("my_dict = _dict()")

	def test_write_wrapper(self) -> None:
		# Allow modifying _dict instance
		safe_exec("_dict().x = 1")

		# dont Allow modifying _dict class
		self.assertRaises(Exception, safe_exec, "_dict.x = 1")

	def test_print(self) -> None:
		test_str = frappe.generate_hash()
		safe_exec(f"print('{test_str}')")
		self.assertEqual(frappe.local.debug_log[-1], test_str)


class TestNoSafeExec(IntegrationTestCase):
	def test_safe_exec_disabled_by_default(self) -> None:
		self.assertRaises(ServerScriptNotEnabled, safe_exec, "pass")
