# Copyright (c) 2019, nts Technologies and Contributors
# License: MIT. See LICENSE
import requests

import nts
from nts.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from nts.ntsclient import ntsClient, ntsException
from nts.tests.utils import ntsTestCase
from nts.utils import get_site_url

scripts = [
	dict(
		name="test_todo",
		script_type="DocType Event",
		doctype_event="Before Insert",
		reference_doctype="ToDo",
		script="""
if "test" in doc.description:
	doc.status = 'Closed'
""",
	),
	dict(
		name="test_todo_validate",
		script_type="DocType Event",
		doctype_event="Before Insert",
		reference_doctype="ToDo",
		script="""
if "validate" in doc.description:
	raise nts.ValidationError
""",
	),
	dict(
		name="test_api",
		script_type="API",
		api_method="test_server_script",
		allow_guest=1,
		script="""
nts.response['message'] = 'hello'
""",
	),
	dict(
		name="test_return_value",
		script_type="API",
		api_method="test_return_value",
		allow_guest=1,
		script="""
nts.flags = 'hello'
""",
	),
	dict(
		name="test_permission_query",
		script_type="Permission Query",
		reference_doctype="ToDo",
		script="""
conditions = '1 = 1'
""",
	),
	dict(
		name="test_invalid_namespace_method",
		script_type="DocType Event",
		doctype_event="Before Insert",
		reference_doctype="Note",
		script="""
nts.method_that_doesnt_exist("do some magic")
""",
	),
	dict(
		name="test_todo_commit",
		script_type="DocType Event",
		doctype_event="Before Save",
		reference_doctype="ToDo",
		disabled=1,
		script="""
nts.db.commit()
""",
	),
	dict(
		name="test_add_index",
		script_type="DocType Event",
		doctype_event="Before Save",
		reference_doctype="ToDo",
		disabled=1,
		script="""
nts.db.add_index("Todo", ["color", "date"])
""",
	),
	dict(
		name="test_before_rename",
		script_type="DocType Event",
		doctype_event="After Rename",
		reference_doctype="Role",
		script="""
doc.desk_access =0
doc.save()
""",
	),
	dict(
		name="test_after_rename",
		script_type="DocType Event",
		doctype_event="After Rename",
		reference_doctype="Role",
		script="""
doc.disabled =1
doc.save()
""",
	),
]


class TestServerScript(ntsTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		nts.db.truncate("Server Script")
		nts.get_doc("User", "Administrator").add_roles("Script Manager")
		for script in scripts:
			script_doc = nts.get_doc(doctype="Server Script")
			script_doc.update(script)
			script_doc.insert()
		cls.enable_safe_exec()
		nts.db.commit()
		return super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		nts.db.commit()
		nts.db.truncate("Server Script")
		nts.cache.delete_value("server_script_map")

	def setUp(self):
		nts.cache.delete_value("server_script_map")

	def test_doctype_event(self):
		todo = nts.get_doc(dict(doctype="ToDo", description="hello")).insert()
		self.assertEqual(todo.status, "Open")

		todo = nts.get_doc(dict(doctype="ToDo", description="test todo")).insert()
		self.assertEqual(todo.status, "Closed")

		self.assertRaises(
			nts.ValidationError, nts.get_doc(dict(doctype="ToDo", description="validate me")).insert
		)

		role = nts.get_doc(doctype="Role", role_name="_Test Role 9").insert(ignore_if_duplicate=True)
		role.rename("_Test Role 10")
		role.reload()
		self.assertEqual(role.disabled, 1)
		self.assertEqual(role.desk_access, 0)

	def test_api(self):
		response = requests.post(get_site_url(nts.local.site) + "/api/method/test_server_script")
		self.assertEqual(response.status_code, 200)
		self.assertEqual("hello", response.json()["message"])

	def test_api_return(self):
		self.assertEqual(nts.get_doc("Server Script", "test_return_value").execute_method(), "hello")

	def test_permission_query(self):
		if nts.conf.db_type == "mariadb":
			self.assertTrue("where (1 = 1)" in nts.db.get_list("ToDo", run=False))
		else:
			self.assertTrue("where (1 = '1')" in nts.db.get_list("ToDo", run=False))
		self.assertTrue(isinstance(nts.db.get_list("ToDo"), list))

	def test_attribute_error(self):
		"""Raise AttributeError if method not found in Namespace"""
		note = nts.get_doc({"doctype": "Note", "title": "Test Note: Server Script"})
		self.assertRaises(AttributeError, note.insert)

	def test_syntax_validation(self):
		server_script = scripts[0]
		server_script["script"] = "js || code.?"

		with self.assertRaises(nts.ValidationError) as se:
			nts.get_doc(doctype="Server Script", **server_script).insert()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)

	def test_commit_in_doctype_event(self):
		server_script = nts.get_doc("Server Script", "test_todo_commit")
		server_script.disabled = 0
		server_script.save()

		self.assertRaises(AttributeError, nts.get_doc(dict(doctype="ToDo", description="test me")).insert)

		server_script.disabled = 1
		server_script.save()

	def test_add_index_in_doctype_event(self):
		server_script = nts.get_doc("Server Script", "test_add_index")
		server_script.disabled = 0
		server_script.save()

		self.assertRaises(AttributeError, nts.get_doc(dict(doctype="ToDo", description="test me")).insert)

		server_script.disabled = 1
		server_script.save()

	def test_restricted_qb(self):
		todo = nts.get_doc(doctype="ToDo", description="QbScriptTestNote")
		todo.insert()

		script = nts.get_doc(
			doctype="Server Script",
			name="test_qb_restrictions",
			script_type="API",
			api_method="test_qb_restrictions",
			allow_guest=1,
			# whitelisted update
			script=f"""
nts.db.set_value("ToDo", "{todo.name}", "description", "safe")
""",
		)
		script.insert()
		script.execute_method()

		todo.reload()
		self.assertEqual(todo.description, "safe")

		# unsafe update
		script.script = f"""
todo = nts.qb.DocType("ToDo")
nts.qb.update(todo).set(todo.description, "unsafe").where(todo.name == "{todo.name}").run()
"""
		script.save()
		self.assertRaises(nts.PermissionError, script.execute_method)
		todo.reload()
		self.assertEqual(todo.description, "safe")

		# safe select
		script.script = f"""
todo = nts.qb.DocType("ToDo")
nts.qb.from_(todo).select(todo.name).where(todo.name == "{todo.name}").run()
"""
		script.save()
		script.execute_method()

	def test_scripts_all_the_way_down(self):
		# why not
		script = nts.get_doc(
			doctype="Server Script",
			name="test_nested_scripts_1",
			script_type="API",
			api_method="test_nested_scripts_1",
			script="""log("nothing")""",
		)
		script.insert()
		script.execute_method()

		script = nts.get_doc(
			doctype="Server Script",
			name="test_nested_scripts_2",
			script_type="API",
			api_method="test_nested_scripts_2",
			script="""nts.call("test_nested_scripts_1")""",
		)
		script.insert()
		script.execute_method()

	def test_server_script_rate_limiting(self):
		script1 = nts.get_doc(
			doctype="Server Script",
			name="rate_limited_server_script",
			script_type="API",
			enable_rate_limit=1,
			allow_guest=1,
			rate_limit_count=5,
			api_method="rate_limited_endpoint",
			script="""nts.flags = {"test": True}""",
		)

		script1.insert()

		script2 = nts.get_doc(
			doctype="Server Script",
			name="rate_limited_server_script2",
			script_type="API",
			enable_rate_limit=1,
			allow_guest=1,
			rate_limit_count=5,
			api_method="rate_limited_endpoint2",
			script="""nts.flags = {"test": False}""",
		)

		script2.insert()

		nts.db.commit()

		site = nts.utils.get_site_url(nts.local.site)
		client = ntsClient(site)

		# Exhaust rate limit
		for _ in range(5):
			client.get_api(script1.api_method)

		self.assertRaises(ntsException, client.get_api, script1.api_method)

		# Exhaust rate limit
		for _ in range(5):
			client.get_api(script2.api_method)

		self.assertRaises(ntsException, client.get_api, script2.api_method)

		script1.delete()
		script2.delete()
		nts.db.commit()

	def test_server_script_scheduled(self):
		scheduled_script = nts.get_doc(
			doctype="Server Script",
			name="scheduled_script_wo_cron",
			script_type="Scheduler Event",
			script="""nts.flags = {"test": True}""",
			event_frequency="Hourly",
		).insert()

		cron_script = nts.get_doc(
			doctype="Server Script",
			name="scheduled_script_w_cron",
			script_type="Scheduler Event",
			script="""nts.flags = {"test": True}""",
			event_frequency="Cron",
			cron_format="0 0 1 1 *",  # 1st january
		).insert()

		# Ensure that jobs remain in DB after migrate
		sync_jobs()
		self.assertTrue(nts.db.exists("Scheduled Job Type", {"server_script": scheduled_script.name}))

		cron_job_name = nts.db.get_value("Scheduled Job Type", {"server_script": cron_script.name})
		self.assertTrue(cron_job_name)

		cron_job = nts.get_doc("Scheduled Job Type", cron_job_name)
		self.assertEqual(cron_job.next_execution.day, 1)
		self.assertEqual(cron_job.next_execution.month, 1)

		cron_script.cron_format = "0 0 2 1 *"  # 2nd january
		cron_script.save()
		cron_job.reload()
		self.assertEqual(cron_job.next_execution.day, 2)
