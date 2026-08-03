import types

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.jinja import get_jenv, render_template
from frappe.utils.safe_exec import SafeDoc, ServerScriptNotEnabled, get_safe_globals, safe_exec


class TestSafeExec(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def test_import_fails(self):
		self.assertRaises(ImportError, safe_exec, "import os")

	def test_internal_attributes(self):
		self.assertRaises(SyntaxError, safe_exec, "().__class__.__call__")

	def test_utils(self):
		_locals = dict(out=None)
		safe_exec("""out = frappe.utils.cint("1")""", None, _locals)
		self.assertEqual(_locals["out"], 1)

	def test_safe_eval(self):
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

	def test_safe_eval_wal(self):
		self.assertRaises(SyntaxError, frappe.safe_eval, "(x := (40+2))")

	def test_sql(self):
		_locals = dict(out=None)
		safe_exec(
			"""out = frappe.db.sql("select name from tabDocType where name='DocType'")""", None, _locals
		)
		self.assertEqual(_locals["out"][0][0], "DocType")

		self.assertRaises(
			frappe.PermissionError, safe_exec, 'frappe.db.sql("update tabToDo set description=NULL")'
		)

	def test_query_builder(self):
		_locals = dict(out=None)
		safe_exec(
			script="""out = frappe.qb.from_("User").select(frappe.qb.terms.PseudoColumn("Max(name)")).run()""",
			_globals=None,
			_locals=_locals,
		)
		self.assertEqual(frappe.db.sql("SELECT Max(name) FROM tabUser"), _locals["out"])

	def test_safe_query_builder(self):
		self.assertRaises(frappe.PermissionError, safe_exec, """frappe.qb.from_("User").delete().run()""")

	def test_safe_query_builder_in_render(self):
		self.assertRaises(
			frappe.PermissionError,
			render_template,
			""" {{ frappe.qb.from_("User").delete().run() }} """,
		)

		# Allowed read query
		frappe.render_template(""" {{ frappe.qb.from_("User").select("*").run() }} """)

	def test_call(self):
		# call non whitelisted method
		self.assertRaises(frappe.PermissionError, safe_exec, """frappe.call("frappe.get_user")""")

		# call whitelisted method
		safe_exec("""frappe.call("ping")""")

	def test_enqueue(self):
		# enqueue non whitelisted method
		self.assertRaises(
			frappe.PermissionError, safe_exec, """frappe.enqueue("frappe.get_user", now=True)"""
		)

		# enqueue whitelisted method
		safe_exec("""frappe.enqueue("ping", now=True)""")

	def test_ensure_getattrable_globals(self):
		def check_safe(objects):
			for obj in objects:
				if isinstance(obj, types.ModuleType | types.CodeType | types.TracebackType | types.FrameType):
					self.fail(f"{obj} wont work in safe exec.")
				elif isinstance(obj, dict):
					check_safe(obj.values())

		check_safe(get_safe_globals().values())

	def test_unsafe_objects(self):
		unsafe_global = {"frappe": frappe}
		self.assertRaises(SyntaxError, safe_exec, """frappe.msgprint("Hello")""", unsafe_global)

	def test_attrdict(self):
		# jinja
		frappe.render_template("{% set my_dict = _dict() %} {{- my_dict.works -}}")

		# RestrictedPython
		safe_exec("my_dict = _dict()")

	def test_write_wrapper(self):
		# Allow modifying _dict instance
		safe_exec("_dict().x = 1")

		# dont Allow modifying _dict class
		self.assertRaises(Exception, safe_exec, "_dict.x = 1")

	def test_print(self):
		test_str = frappe.generate_hash()
		safe_exec(f"print('{test_str}')")
		self.assertEqual(frappe.local.debug_log[-1], test_str)


class TestSafeDoc(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("DocType", "Test SafeDoc Row"):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"module": "Core",
					"name": "Test SafeDoc Row",
					"istable": 1,
					"custom": 1,
					"fields": [
						{"fieldname": "description", "fieldtype": "Data", "label": "Description"},
						{"fieldname": "rate", "fieldtype": "Float", "label": "Rate"},
						{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount"},
					],
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("DocType", "Test SafeDoc Parent"):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"module": "Core",
					"name": "Test SafeDoc Parent",
					"custom": 1,
					"fields": [
						{"fieldname": "absolute_value", "fieldtype": "Check", "label": "Absolute Value"},
						{
							"fieldname": "rows",
							"fieldtype": "Table",
							"label": "Rows",
							"options": "Test SafeDoc Row",
						},
					],
				}
			).insert(ignore_permissions=True)

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc("DocType", "Test SafeDoc Parent", ignore_missing=True, force=True)
		frappe.delete_doc("DocType", "Test SafeDoc Row", ignore_missing=True, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def _make_parent(self, absolute_value=0):
		return SafeDoc(
			{
				"doctype": "Test SafeDoc Parent",
				"name": "TEST-001",
				"absolute_value": absolute_value,
				"rows": [
					{
						"doctype": "Test SafeDoc Row",
						"description": "Test Row",
						"rate": 18.0,
						"amount": -90.0,
					}
				],
			}
		)

	def test_safe_doc_instance(self):
		from frappe.utils.safe_exec import get_doc_as_dict

		doc = get_doc_as_dict("User", frappe.session.user)
		self.assertIsInstance(doc, SafeDoc)

		parent = self._make_parent()
		row = parent.get("rows")[0]
		self.assertIsInstance(row, SafeDoc)

	def test_parent_doc_attr(self):
		parent = self._make_parent()
		row = parent.get("rows")[0]
		self.assertIs(row.parent_doc, parent)

	def test_safe_get_formatted(self):
		from frappe.utils.safe_exec import get_doc_as_dict

		doc = get_doc_as_dict("User", frappe.session.user)
		# email is a Data field — formatted value equals the raw value
		self.assertEqual(doc.get_formatted("email"), doc.get("email"))

		parent = self._make_parent()
		row = parent.get("rows")[0]
		result = row.get_formatted("rate")
		self.assertIn("18", result)

		result = row.get_formatted("amount", currency="INR")
		self.assertIn("₹", result)

	def test_get_label_from_fieldname(self):
		from frappe.utils.safe_exec import get_doc_as_dict

		doc = get_doc_as_dict("User", frappe.session.user)
		self.assertEqual(doc.get_label_from_fieldname("email"), "Email")
		self.assertIsNone(doc.get_label_from_fieldname("nonexistent_field"))

		parent = self._make_parent()
		row = parent.get("rows")[0]
		self.assertEqual(row.get_label_from_fieldname("rate"), "Rate")
		self.assertEqual(row.get_label_from_fieldname("amount"), "Amount")

	def test_meta_property(self):
		from frappe.utils.safe_exec import get_doc_as_dict

		doc = get_doc_as_dict("User", frappe.session.user)
		# meta returns a plain dict, not a live Meta object
		self.assertIsInstance(doc.meta, frappe._dict)
		self.assertIsNotNone(doc.meta.get("is_submittable"))

		# works on child rows too
		parent = self._make_parent()
		row = parent.get("rows")[0]
		self.assertIsInstance(row.meta, frappe._dict)
		self.assertEqual(row.meta.get("name"), "Test SafeDoc Row")

		# no mutating methods exposed
		self.assertIsNone(doc.meta.get("save"))
		self.assertIsNone(doc.meta.get("insert"))

	def test_in_format_data(self):
		parent = self._make_parent()
		row = parent.get("rows")[0]

		# no format_data_map set — all fields visible
		self.assertTrue(row.in_format_data("rate"))
		self.assertTrue(row.in_format_data("amount"))

		# parent itself has no parent_doc — falls back to self
		self.assertTrue(parent.in_format_data("absolute_value"))

		# with format_data_map on parent — only listed fields visible
		parent["format_data_map"] = {"rate": True}
		self.assertTrue(row.in_format_data("rate"))
		self.assertFalse(row.in_format_data("amount"))

	def test_is_print_hide(self):
		parent = self._make_parent()
		row = parent.get("rows")[0]

		# field with no print_hide set — should not be hidden
		self.assertFalse(row.is_print_hide("description"))

		# explicit df with print_hide=1
		df = frappe._dict(print_hide=1, print_hide_if_no_value=0)
		self.assertTrue(row.is_print_hide("description", df=df))

	def test_absolute_value_from_parent(self):
		parent = self._make_parent(absolute_value=1)
		row = parent.get("rows")[0]
		result = row.get_formatted("amount")
		self.assertNotIn("-", result)

	def test_absolute_value_not_set(self):
		parent = self._make_parent(absolute_value=0)
		row = parent.get("rows")[0]
		result = row.get_formatted("amount")
		self.assertIn("-", result)

	def test_jinja_get_formatted_in_template(self):
		expected = frappe.db.get_value("User", frappe.session.user, "first_name")
		result = render_template(
			"{{ frappe.get_doc('User', frappe.session.user).get_formatted('first_name') }}",
			restrict_globals=True,
		)
		self.assertEqual(result.strip(), expected)


class TestNoSafeExec(IntegrationTestCase):
	def test_safe_exec_disabled_by_default(self):
		self.assertRaises(ServerScriptNotEnabled, safe_exec, "pass")


class TestJinjaGlobals(IntegrationTestCase):
	def test_jenv_thread_safety(self):
		first = get_jenv()
		# reinit to create a new local ctx, this "simulates" two request running in two diff
		# thread.
		frappe.init(frappe.local.site, force=True)
		frappe.connect()
		second = get_jenv()
		self.assertIsNot(first, second)
		self.assertIsNot(first.globals, second.globals)
		self.assertIsNot(first.filters, second.filters)
		self.assertIsNot(first.globals["frappe"], second.globals["frappe"])
		self.assertIsNot(first.globals["frappe"]["form_dict"], second.globals["frappe"]["form_dict"])

	def test_globals_override(self):
		"""Test that when restrict_globals is parsed, the correct globals are injected."""
		from frappe.utils.safe_exec import FrappeClient, safe_get_all

		jenv_restricted = get_jenv(restrict_globals=True)
		self.assertIs(jenv_restricted.globals["frappe"]["get_all"], safe_get_all)
		with self.assertRaises(KeyError):
			jenv_restricted.globals["FrappeClient"]

		jenv_unrestricted = get_jenv(restrict_globals=False)
		self.assertIs(jenv_unrestricted.globals["frappe"]["get_all"], frappe.get_all)
		self.assertIs(jenv_unrestricted.globals["FrappeClient"], FrappeClient)  # test exclusivity

		self.assertIsNot(jenv_restricted, jenv_unrestricted)  # globals cache check
		self.assertIsNot(jenv_restricted.globals, jenv_unrestricted.globals)
		self.assertIs(get_jenv(restrict_globals=True), jenv_restricted)
		self.assertIs(get_jenv(restrict_globals=False), jenv_unrestricted)
