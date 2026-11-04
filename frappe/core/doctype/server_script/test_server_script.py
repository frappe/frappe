# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import requests
from cryptography.fernet import Fernet

import frappe
from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType, sync_jobs
from frappe.core.doctype.server_script.server_script import ServerScript
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.frappeclient import FrappeClient, FrappeException
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import get_site_url
from frappe.utils.password import Auth, encrypt, get_decrypted_password
from frappe.utils.safe_exec import get_safe_globals, safe_exec

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
	raise frappe.ValidationError
""",
	),
	dict(
		name="test_api",
		script_type="API",
		api_method="test_server_script",
		allow_guest=1,
		script="""
frappe.response['message'] = 'hello'
""",
	),
	dict(
		name="test_return_value",
		script_type="API",
		api_method="test_return_value",
		allow_guest=1,
		script="""
frappe.flags = 'hello'
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
frappe.method_that_doesnt_exist("do some magic")
""",
	),
	dict(
		name="test_todo_commit",
		script_type="DocType Event",
		doctype_event="Before Save",
		reference_doctype="ToDo",
		disabled=1,
		script="""
frappe.db.commit()
""",
	),
	dict(
		name="test_add_index",
		script_type="DocType Event",
		doctype_event="Before Save",
		reference_doctype="ToDo",
		disabled=1,
		script="""
frappe.db.add_index("Todo", ["color", "date"])
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


class TestServerScript(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.truncate("Server Script")
		frappe.get_doc("User", "Administrator").add_roles("Script Manager")
		for script in scripts:
			script_doc = frappe.get_doc(doctype="Server Script")
			script_doc.update(script)
			script_doc.insert()
		cls.enterClassContext(cls.enable_safe_exec())
		frappe.db.commit()
		return super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("__Auth", {"doctype": "Server Script Variable"})
		frappe.db.commit()
		frappe.db.truncate("Server Script")
		frappe.db.truncate("Server Script Variable")
		frappe.client_cache.delete_value("server_script_map")

	def setUp(self):
		frappe.client_cache.delete_value("server_script_map")

	def test_doctype_event(self):
		todo = frappe.get_doc(doctype="ToDo", description="hello").insert()
		self.assertEqual(todo.status, "Open")

		todo = frappe.get_doc(doctype="ToDo", description="test todo").insert()
		self.assertEqual(todo.status, "Closed")

		self.assertRaises(
			frappe.ValidationError, frappe.get_doc(doctype="ToDo", description="validate me").insert
		)

		role = frappe.get_doc(doctype="Role", role_name="_Test Role 9").insert(ignore_if_duplicate=True)
		role.rename("_Test Role 10")
		role.reload()
		self.assertEqual(role.disabled, 1)
		self.assertEqual(role.desk_access, 0)

	@requires_test_service(TestService.WEB_SERVER)
	def test_api(self):
		response = requests.post(get_site_url(frappe.local.site) + "/api/method/test_server_script")
		self.assertEqual(response.status_code, 200)
		self.assertEqual("hello", response.json()["message"])

	def test_api_return(self):
		self.assertEqual(frappe.get_doc("Server Script", "test_return_value").execute_method(), "hello")

	def test_permission_query(self):
		sql = frappe.db.get_list("ToDo", run=False).get_sql()
		self.assertTrue("where (1 = 1)" in sql.lower())
		self.assertTrue(isinstance(frappe.db.get_list("ToDo"), list))

	def test_attribute_error(self):
		"""Raise AttributeError if method not found in Namespace"""
		note = frappe.get_doc({"doctype": "Note", "title": "Test Note: Server Script"})
		self.assertRaises(AttributeError, note.insert)

	def test_syntax_validation(self):
		server_script = scripts[0]
		server_script["script"] = "js || code.?"

		with self.assertRaises(frappe.ValidationError) as se:
			frappe.get_doc(doctype="Server Script", **server_script).insert()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)

	def test_commit_in_doctype_event(self):
		server_script = frappe.get_doc("Server Script", "test_todo_commit")
		server_script.disabled = 0
		server_script.save()

		self.assertRaises(AttributeError, frappe.get_doc(doctype="ToDo", description="test me").insert)

		server_script.disabled = 1
		server_script.save()

	def test_add_index_in_doctype_event(self):
		server_script = frappe.get_doc("Server Script", "test_add_index")
		server_script.disabled = 0
		server_script.save()

		self.assertRaises(AttributeError, frappe.get_doc(doctype="ToDo", description="test me").insert)

		server_script.disabled = 1
		server_script.save()

	def test_restricted_qb(self):
		todo = frappe.get_doc(doctype="ToDo", description="QbScriptTestNote")
		todo.insert()

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_qb_restrictions",
			script_type="API",
			api_method="test_qb_restrictions",
			allow_guest=1,
			# whitelisted update
			script=f"""
frappe.db.set_value("ToDo", "{todo.name}", "description", "safe")
""",
		)
		script.insert()
		script.execute_method()

		todo.reload()
		self.assertEqual(todo.description, "safe")

		# unsafe update
		script.script = f"""
todo = frappe.qb.DocType("ToDo")
frappe.qb.update(todo).set(todo.description, "unsafe").where(todo.name == "{todo.name}").run()
"""
		script.save()
		self.assertRaises(frappe.PermissionError, script.execute_method)
		todo.reload()
		self.assertEqual(todo.description, "safe")

		# safe select
		script.script = f"""
todo = frappe.qb.DocType("ToDo")
frappe.qb.from_(todo).select(todo.name).where(todo.name == "{todo.name}").run()
"""
		script.save()
		script.execute_method()

	def test_scripts_all_the_way_down(self):
		# why not
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_nested_scripts_1",
			script_type="API",
			api_method="test_nested_scripts_1",
			script="""log("nothing")""",
		)
		script.insert()
		script.execute_method()

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_nested_scripts_2",
			script_type="API",
			api_method="test_nested_scripts_2",
			script="""frappe.call("test_nested_scripts_1")""",
		)
		script.insert()
		script.execute_method()

	@requires_test_service(TestService.WEB_SERVER)
	def test_server_script_rate_limiting(self):
		script1 = frappe.get_doc(
			doctype="Server Script",
			name="rate_limited_server_script",
			script_type="API",
			enable_rate_limit=1,
			allow_guest=1,
			rate_limit_count=5,
			api_method="rate_limited_endpoint",
			script="""frappe.flags = {"test": True}""",
		)

		script1.insert()

		script2 = frappe.get_doc(
			doctype="Server Script",
			name="rate_limited_server_script2",
			script_type="API",
			enable_rate_limit=1,
			allow_guest=1,
			rate_limit_count=5,
			api_method="rate_limited_endpoint2",
			script="""frappe.flags = {"test": False}""",
		)

		script2.insert()

		# Rate-limit counters outlive database rollbacks, so isolate this test
		# from earlier runs. The final part of the key is the request IP.
		for script in (script1, script2):
			counter_prefix = f"rl:server_script:{script.name}:"
			frappe.cache.delete_keys(counter_prefix)
			self.addCleanup(frappe.cache.delete_keys, counter_prefix)

		frappe.db.commit()

		site = frappe.utils.get_site_url(frappe.local.site)
		client = FrappeClient(site)

		# Exhaust rate limit
		for _ in range(5):
			client.get_api(script1.api_method)

		self.assertRaises(FrappeException, client.get_api, script1.api_method)

		# Exhaust rate limit
		for _ in range(5):
			client.get_api(script2.api_method)

		self.assertRaises(FrappeException, client.get_api, script2.api_method)

		script1.delete()
		script2.delete()
		frappe.db.commit()

	def test_server_script_scheduled(self):
		scheduled_script = frappe.get_doc(
			doctype="Server Script",
			name="scheduled_script_wo_cron",
			script_type="Scheduler Event",
			script="""frappe.flags = {"test": True}""",
			event_frequency="Hourly",
		).insert()

		cron_script = frappe.get_doc(
			doctype="Server Script",
			name="scheduled_script_w_cron",
			script_type="Scheduler Event",
			script="""frappe.flags = {"test": True}""",
			event_frequency="Cron",
			cron_format="0 0 1 1 *",  # 1st january
		).insert()

		# Ensure that jobs remain in DB after migrate
		sync_jobs()
		self.assertTrue(frappe.db.exists("Scheduled Job Type", {"server_script": scheduled_script.name}))

		cron_job_name = frappe.db.get_value("Scheduled Job Type", {"server_script": cron_script.name})
		self.assertTrue(cron_job_name)

		cron_job = frappe.get_doc("Scheduled Job Type", cron_job_name)
		self.assertEqual(cron_job.next_execution.day, 1)
		self.assertEqual(cron_job.next_execution.month, 1)

		cron_script.cron_format = "0 0 2 1 *"  # 2nd january
		cron_script.save()

		updated_cron_job_name = frappe.db.get_value("Scheduled Job Type", {"server_script": cron_script.name})
		updated_cron_job = frappe.get_doc("Scheduled Job Type", updated_cron_job_name)
		self.assertEqual(updated_cron_job.next_execution.day, 2)

	def test_server_script_state_changes(self):
		script: ServerScript = frappe.get_doc(
			doctype="Server Script",
			name="scheduled_script_state_change",
			script_type="Scheduler Event",
			script="""frappe.flags = {"test": True}""",
			event_frequency="Hourly",
		).insert()

		job: ScheduledJobType = frappe.get_doc("Scheduled Job Type", {"server_script": script.name})

		script.script_type = "API"
		script.save()
		self.assertTrue(job.reload().stopped)

		script.script_type = "Scheduler Event"
		script.save()
		self.assertFalse(job.reload().stopped)

		# Change to different frequency
		script.event_frequency = "Monthly"
		script.save()
		self.assertEqual(job.reload().frequency, "Monthly")

		# change cron expr
		script.event_frequency = "Cron"
		script.cron_format = "* * * * *"
		script.save()
		self.assertEqual(job.reload().frequency, "Cron")
		self.assertEqual(job.reload().cron_format, script.cron_format)

		script.queue = "long"
		script.save()
		self.assertEqual(job.reload().queue, "long")
		self.assertEqual(job.get_queue_name(), "long")

		script.queue = ""
		script.save()
		self.assertFalse(job.reload().queue)
		self.assertEqual(job.get_queue_name(), "default")

		# manually disable

		script.disabled = 1
		script.save()
		self.assertTrue(job.reload().stopped)

		script.disabled = 0
		script.save()
		self.assertFalse(job.reload().stopped)

	def test_env_variables(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variables",
			script_type="API",
			api_method="test_env_variables",
			script="frappe.flags = frappe.env.API_TOKEN",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		).insert()

		stored_value = frappe.db.get_value("Server Script Variable", script.variables[0].name, "value")
		self.assertNotIn("s3cr3t", stored_value)
		self.assertNotIn("env", get_safe_globals().frappe)

		with self.set_user("test@example.com"):
			self.assertEqual(frappe.get_doc("Server Script", script.name).execute_method(), "s3cr3t")

	def test_env_variable_get_password_is_refused(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variables_owner",
			script_type="API",
			api_method="test_env_variables_owner",
			script="frappe.flags = frappe.env.API_TOKEN",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		).insert()
		other_script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variables_reader",
			script_type="API",
			api_method="test_env_variables_reader",
			script=f'frappe.flags = frappe.get_doc("Server Script", "{script.name}").variables[0].get_password("value")',
		).insert()

		with self.set_user("test@example.com"):
			self.assertRaises(frappe.PermissionError, other_script.execute_method)
			self.assertRaises(
				frappe.PermissionError,
				safe_exec,
				f'frappe.get_doc("Server Script Variable", "{script.variables[0].name}").get_password("value")',
			)
			self.assertEqual(script.execute_method(), "s3cr3t")

	def test_env_variables_with_prompt_name(self):
		script = frappe.get_doc(
			{
				"doctype": "Server Script",
				"__newname": "test_env_variables_with_prompt_name",
				"script_type": "API",
				"api_method": "test_env_variables_with_prompt_name",
				"script": "frappe.flags = frappe.env.API_TOKEN",
				"variables": [{"key": "API_TOKEN", "value": "s3cr3t"}],
			}
		).insert()

		self.assertEqual(script.name, "test_env_variables_with_prompt_name")
		with self.set_user("test@example.com"):
			self.assertEqual(script.execute_method(), "s3cr3t")

	def test_env_variables_with_name_set(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variables_with_name_set",
			script_type="API",
			api_method="test_env_variables_with_name_set",
			script="frappe.flags = frappe.env.API_TOKEN + frappe.env.API_SECRET",
			variables=[
				{"key": "API_TOKEN", "value": "s3cr3t"},
				{"name": "test_env_variables_with_name_set_row", "key": "API_SECRET", "value": "p4ss"},
			],
		)
		script.flags.name_set = True
		script.insert()

		self.assertEqual(script.name, "test_env_variables_with_name_set")
		self.assertEqual(script.variables[1].name, "test_env_variables_with_name_set_row")
		with self.set_user("test@example.com"):
			self.assertEqual(frappe.get_doc("Server Script", script.name).execute_method(), "s3cr3tp4ss")

	def test_missing_env_variable(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_missing_env_variable",
			script_type="API",
			api_method="test_missing_env_variable",
			script="frappe.flags = frappe.env.API_TOKEN",
		).insert()

		with self.set_user("test@example.com"):
			self.assertRaisesRegex(frappe.ValidationError, "API_TOKEN", script.execute_method)

	def test_env_variable_without_saved_value(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variable_without_saved_value",
			script_type="API",
			api_method="test_env_variable_without_saved_value",
			script="frappe.flags = frappe.env.API_TOKEN",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		).insert()
		frappe.db.delete("__Auth", {"doctype": "Server Script Variable", "name": script.variables[0].name})

		with self.set_user("test@example.com"):
			self.assertRaisesRegex(frappe.ValidationError, "API_TOKEN", script.execute_method)

	def test_env_variable_that_cannot_be_decrypted(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variable_that_cannot_be_decrypted",
			script_type="API",
			api_method="test_env_variable_that_cannot_be_decrypted",
			script="frappe.flags = frappe.env.API_TOKEN",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		).insert()
		(
			frappe.qb.update(Auth)
			.set(Auth.password, encrypt("s3cr3t", encryption_key=Fernet.generate_key().decode()))
			.where((Auth.doctype == "Server Script Variable") & (Auth.name == script.variables[0].name))
		).run()

		with self.set_user("test@example.com"):
			self.assertRaisesRegex(frappe.ValidationError, "Encryption key is invalid", script.execute_method)

	def test_env_variable_key_validation(self):
		invalid_variables = [
			[{"key": "API TOKEN", "value": "s3cr3t"}],
			[{"key": "1_TOKEN", "value": "s3cr3t"}],
			[{"key": "_TOKEN", "value": "s3cr3t"}],
			[{"key": "class", "value": "s3cr3t"}],
			[{"key": "format", "value": "s3cr3t"}],
			[{"key": "f_code", "value": "s3cr3t"}],
			[{"key": "co_code", "value": "s3cr3t"}],
			[{"key": "TOKEN__roles__", "value": "s3cr3t"}],
			[{"key": "TOKEN\n", "value": "s3cr3t"}],
			[{"key": "TOKEN", "value": "a"}, {"key": "TOKEN", "value": "b"}],
		]
		for variables in invalid_variables:
			script = frappe.get_doc(
				doctype="Server Script",
				name="test_env_variable_key_validation",
				script_type="API",
				api_method="test_env_variable_key_validation",
				script="pass",
				variables=variables,
			)
			with self.subTest(variables=variables):
				self.assertRaises(frappe.ValidationError, script.insert)

	def test_env_variable_values_are_deleted(self):
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_env_variable_values_are_deleted",
			script_type="API",
			api_method="test_env_variable_values_are_deleted",
			script="pass",
			variables=[{"key": "OLD_TOKEN", "value": "old"}, {"key": "NEW_TOKEN", "value": "new"}],
		).insert()
		old_row, new_row = script.variables

		script.remove(old_row)
		script.save()
		self.assertIsNone(
			get_decrypted_password(old_row.doctype, old_row.name, "value", raise_exception=False)
		)
		self.assertEqual(get_decrypted_password(new_row.doctype, new_row.name, "value"), "new")

		script.delete()
		self.assertIsNone(
			get_decrypted_password(new_row.doctype, new_row.name, "value", raise_exception=False)
		)

	def test_file_sourced_script(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_sourced",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
		frappe.client_cache.delete_value("server_script_map")

		self.assertTrue(os.path.exists(path))

		with open(path, "w") as f:
			f.write("doc.status = 'Cancelled'\n")
		self.assertEqual(frappe.get_doc(doctype="ToDo", description="file one").insert().status, "Cancelled")

		with open(path, "w") as f:
			f.write("doc.status = 'Closed'\n")
		os.utime(path, ns=(1, os.stat(path).st_mtime_ns + 1_000_000))
		self.assertEqual(frappe.get_doc(doctype="ToDo", description="file two").insert().status, "Closed")

		script.save()
		self.assertIn("doc.status = 'Closed'", open(path).read())

		os.remove(path)
		with self.assertRaises(frappe.DoesNotExistError):
			frappe.get_doc(doctype="ToDo", description="file three").insert()

	def test_file_sourced_script_body_is_never_stored_in_db(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_sourced_nodb",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script="frappe.throw('from db')",
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
		self.assertEqual(script.script, "")

		frappe.db.set_value("Server Script", script.name, "script", "frappe.throw('from db')")
		script.reload().save()
		self.assertEqual(script.script, "")
		self.assertNotIn("from db", open(path).read())

	def test_file_sourced_script_syntax_error_is_reported(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_sourced_syntax",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
		frappe.client_cache.delete_value("server_script_map")

		with open(path, "w") as f:
			f.write("def broken(:\n")
		with self.assertRaises(frappe.ValidationError):
			script.get_compiled_file_code()

	def test_file_sourced_script_onload_shows_file_body(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_sourced_onload",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		with open(path, "w") as f:
			f.write("doc.status = 'Closed'\n")
		script = frappe.get_doc("Server Script", script.name)
		script.run_method("onload")
		self.assertEqual(script.script, "doc.status = 'Closed'\n")
		self.assertEqual(script.get_onload("file_path"), path)

		script.save()
		self.assertEqual(frappe.db.get_value("Server Script", script.name, "script"), "")

	def test_file_sourced_script_onload_links_to_pilot_editor(self):
		from unittest.mock import patch

		script = frappe.get_doc(
			doctype="Server Script",
			name="test file editor link",
			script_type="API",
			api_method="test_file_editor_link",
			script_source="File",
		).insert()
		self.addCleanup(script.delete)
		pilot_urls = {
			"cloud_server_url": "https://pilot.example.com/",
			"pilot_endpoint": "http://127.0.0.1:7000",
		}

		with patch.dict(frappe.conf, pilot_urls):
			script.run_method("onload")
			self.assertEqual(
				script.get_onload("editor_url"),
				f"https://pilot.example.com/editor/site/{frappe.local.site}?open=test%20file%20editor%20link.py",
			)

		with patch.dict(frappe.conf, pilot_urls):
			del frappe.conf["cloud_server_url"]
			del frappe.conf["pilot_endpoint"]
			script.run_method("onload")
			self.assertIsNone(script.get_onload("editor_url"))

	def test_script_is_required_only_for_database_scripts(self):
		import os

		args = {
			"doctype": "Server Script",
			"script_type": "DocType Event",
			"reference_doctype": "ToDo",
			"doctype_event": "Before Insert",
		}
		with self.assertRaises(frappe.MandatoryError):
			frappe.get_doc(**args, name="test_db_no_body", script_source="Database").insert()

		script = frappe.get_doc(**args, name="test_file_no_body", script_source="File").insert()
		self.addCleanup(script.delete)
		self.addCleanup(lambda: os.path.exists(script.get_file_path()) and os.remove(script.get_file_path()))

	def test_file_script_cannot_switch_back_to_database(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_no_switch_back",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		self.addCleanup(script.delete)
		self.addCleanup(lambda: os.path.exists(script.get_file_path()) and os.remove(script.get_file_path()))

		script.script_source = "Database"
		script.script = "doc.status = 'Closed'"
		with self.assertRaises(frappe.ValidationError):
			script.save()

	def test_database_script_body_moves_to_file_on_switch(self):
		import os

		body = "doc.status = 'Closed'\n"
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_db_to_file_switch",
			script_type="DocType Event",
			script_source="Database",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script=body,
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		script.script_source = "File"
		script.save()
		self.assertEqual(open(path).read(), body)
		self.assertEqual(frappe.db.get_value("Server Script", script.name, "script"), "")

	def test_switch_to_file_refuses_to_overwrite_existing_file(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_db_to_file_existing",
			script_type="DocType Event",
			script_source="Database",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script="doc.status = 'Closed'",
		).insert()
		self.addCleanup(script.delete)
		path = script.get_file_path()
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			f.write("# existing\n")
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		script.script_source = "File"
		with self.assertRaises(frappe.ValidationError):
			script.save()
		self.assertEqual(open(path).read(), "# existing\n")

	def test_deleting_file_script_removes_its_file(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_file_delete",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		path = script.get_file_path()
		self.assertTrue(os.path.exists(path))

		script.delete()
		self.assertFalse(os.path.exists(path))

	def test_deleting_database_script_leaves_files_alone(self):
		import os

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_db_delete",
			script_type="DocType Event",
			script_source="Database",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script="doc.status = 'Closed'",
		).insert()
		path = script.get_file_path()
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			f.write("# unrelated\n")
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		script.delete()
		self.assertTrue(os.path.exists(path))

	def test_delete_file_script_helper(self):
		import os

		from frappe.core.doctype.server_script.server_script import delete_file_script

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_delete_helper_file",
			script_type="DocType Event",
			script_source="File",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		).insert()
		path = script.get_file_path()
		delete_file_script(script.name)
		self.assertFalse(frappe.db.exists("Server Script", script.name))
		self.assertFalse(os.path.exists(path))

	def test_delete_file_script_helper_refuses_database_script(self):
		from frappe.core.doctype.server_script.server_script import delete_file_script

		script = frappe.get_doc(
			doctype="Server Script",
			name="test_delete_helper_db",
			script_type="DocType Event",
			script_source="Database",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script="doc.status = 'Closed'",
		).insert()
		self.addCleanup(script.delete)
		with self.assertRaises(frappe.ValidationError):
			delete_file_script(script.name)
		self.assertTrue(frappe.db.exists("Server Script", script.name))

	def test_delete_file_script_helper_removes_orphan_file(self):
		import os

		from frappe.core.doctype.server_script.server_script import delete_file_script

		path = frappe.get_site_path("server_scripts", "test_orphan_file.py")
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			f.write("# orphan\n")
		delete_file_script("test_orphan_file")
		self.assertFalse(os.path.exists(path))

	def test_only_administrator_can_switch_script_to_file(self):
		user = frappe.get_doc("User", "test@example.com")
		user.add_roles("Script Manager")
		self.addCleanup(user.remove_roles, "Script Manager")
		script = frappe.get_doc(
			doctype="Server Script",
			name="test_switch_needs_admin",
			script_type="DocType Event",
			script_source="Database",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			script="doc.status = 'Closed'",
		).insert()
		self.addCleanup(script.delete)

		with self.set_user("test@example.com"):
			script.script_source = "File"
			with self.assertRaises(frappe.PermissionError):
				script.save()
		self.assertEqual(frappe.db.get_value("Server Script", script.name, "script_source"), "Database")

	def make_file_script(self, name, body="", **fields):
		script = frappe.get_doc(doctype="Server Script", name=name, script_source="File", **fields).insert()
		self.addCleanup(script.delete)
		self.write_file_script(script, body)
		return script

	def write_file_script(self, script, body):
		import os

		path = script.get_file_path()
		with open(path, "w") as f:
			f.write(body)
		os.utime(path, ns=(1, os.stat(path).st_mtime_ns + 1_000_000))
		frappe.client_cache.delete_value("server_script_map")

	def test_file_api_script_over_http(self):
		self.addCleanup(frappe.db.commit)
		script = self.make_file_script(
			"test_file_api",
			"frappe.flags = 'hello from file'\n",
			script_type="API",
			api_method="test_file_api",
			allow_guest=1,
		)
		self.assertEqual(script.execute_method(), "hello from file")
		frappe.db.commit()

		response = requests.post(get_site_url(frappe.local.site) + "/api/method/test_file_api")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["message"], "hello from file")

	def test_file_api_script_guest_access(self):
		self.addCleanup(frappe.db.commit)
		script = self.make_file_script(
			"test_file_api_private",
			"frappe.flags = 'private'\n",
			script_type="API",
			api_method="test_file_api_private",
			allow_guest=0,
		)
		frappe.db.commit()
		url = get_site_url(frappe.local.site) + "/api/method/test_file_api_private"
		self.assertEqual(requests.post(url).status_code, 403)

		script.allow_guest = 1
		script.save()
		frappe.db.commit()
		self.assertEqual(requests.post(url).json()["message"], "private")

	def test_file_api_script_rate_limit(self):
		self.addCleanup(frappe.db.commit)
		script = self.make_file_script(
			"test_file_rate_limited",
			"frappe.flags = 'ok'\n",
			script_type="API",
			api_method="test_file_rate_limited",
			allow_guest=1,
			enable_rate_limit=1,
			rate_limit_count=2,
			rate_limit_seconds=60,
		)
		counter_prefix = f"rl:server_script:{script.name}:"
		frappe.cache.delete_keys(counter_prefix)
		self.addCleanup(frappe.cache.delete_keys, counter_prefix)
		frappe.db.commit()

		client = FrappeClient(get_site_url(frappe.local.site))
		for _ in range(2):
			client.get_api(script.api_method)
		self.assertRaises(FrappeException, client.get_api, script.api_method)

	def test_file_scheduler_script_runs_through_its_job(self):
		description = "scheduled from file"
		body = f'frappe.get_doc({{"doctype": "ToDo", "description": "{description}"}}).insert()\n'
		script = self.make_file_script(
			"test_file_scheduled", body, script_type="Scheduler Event", event_frequency="Hourly"
		)
		self.addCleanup(frappe.db.delete, "ToDo", {"description": description})
		sync_jobs()
		job_name = frappe.db.get_value("Scheduled Job Type", {"server_script": script.name})
		self.assertTrue(job_name)

		frappe.get_doc("Scheduled Job Type", job_name).execute()
		self.assertTrue(frappe.db.exists("ToDo", {"description": description}))
		log = frappe.get_all(
			"Scheduled Job Log",
			filters={"scheduled_job_type": job_name},
			fields=["status"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(log[0].status, "Complete")

	def test_file_scheduler_script_every_frequency(self):
		frequencies = [
			"All",
			"Hourly",
			"Daily",
			"Weekly",
			"Monthly",
			"Yearly",
			"Hourly Long",
			"Daily Long",
			"Weekly Long",
			"Monthly Long",
			"Cron",
		]
		scripts = {}
		for index, frequency in enumerate(frequencies):
			fields = {"cron_format": "0 0 1 1 *"} if frequency == "Cron" else {}
			scripts[frequency] = self.make_file_script(
				f"test_file_freq_{index}",
				"",
				script_type="Scheduler Event",
				event_frequency=frequency,
				**fields,
			)
		sync_jobs()

		for frequency, script in scripts.items():
			with self.subTest(frequency=frequency):
				job_name = frappe.db.get_value("Scheduled Job Type", {"server_script": script.name})
				self.assertTrue(job_name)
				job = frappe.get_doc("Scheduled Job Type", job_name)
				self.assertEqual(job.frequency, frequency)
				if frequency == "Cron":
					self.assertEqual((job.next_execution.day, job.next_execution.month), (1, 1))

	def test_file_permission_query_script(self):
		self.make_file_script(
			"test_file_perm_query",
			'conditions = "(1 = 2)"\n',
			script_type="Permission Query",
			reference_doctype="Note",
		)
		self.assertIn("(1 = 2)", frappe.db.get_list("Note", run=False).get_sql())
		self.assertEqual(frappe.db.get_list("Note"), [])

	def test_file_workflow_task_script(self):
		script = self.make_file_script(
			"test_file_workflow_task",
			'doc.description = "set by file workflow task"\n',
			script_type="Workflow Task",
		)
		todo = frappe.new_doc("ToDo")
		script.execute_workflow_task(todo)
		self.assertEqual(todo.description, "set by file workflow task")

	def test_file_doctype_events(self):
		events = ["Before Insert", "Before Validate", "Before Save", "After Insert", "After Save"]
		delete_events = ["Before Delete", "After Delete"]
		save_body = 'doc.flags.fired = (doc.flags.fired or []) + ["{}"]\n'
		# delete hooks run on a fresh document, so they leave a mark in the database instead
		delete_body = 'frappe.get_doc({{"doctype": "ToDo", "description": "fired {}"}}).insert()\n'
		for index, event in enumerate(events + delete_events):
			body = delete_body if event in delete_events else save_body
			self.make_file_script(
				f"test_file_event_{index}",
				body.format(event),
				script_type="DocType Event",
				reference_doctype="ToDo",
				doctype_event=event,
			)
		self.addCleanup(frappe.db.delete, "ToDo", {"description": ("like", "fired %")})

		todo = frappe.get_doc(doctype="ToDo", description="events from file").insert()
		self.assertEqual(set(todo.flags.fired), set(events))

		todo.delete()
		for event in delete_events:
			self.assertTrue(frappe.db.exists("ToDo", {"description": f"fired {event}"}), event)

	def test_file_doctype_event_cannot_commit(self):
		self.make_file_script(
			"test_file_commit",
			"frappe.db.commit()\n",
			script_type="DocType Event",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
		)
		self.assertRaises(AttributeError, frappe.get_doc(doctype="ToDo", description="commit me").insert)

	def test_disabled_file_script_is_never_dispatched(self):
		import os

		script = self.make_file_script(
			"test_file_disabled",
			"frappe.throw('should not run')\n",
			script_type="DocType Event",
			reference_doctype="ToDo",
			doctype_event="Before Insert",
			disabled=1,
		)
		os.remove(script.get_file_path())
		frappe.get_doc(doctype="ToDo", description="disabled file script").insert()
		self.assertNotIn(script.name, get_server_script_map().get("ToDo", {}).get("Before Insert", []))

	def test_every_script_type_fails_loudly_on_bad_file(self):
		import os

		cases = {
			"API": (
				{"script_type": "API", "api_method": "test_file_loud_api"},
				lambda script: script.execute_method(),
			),
			"Scheduler Event": (
				{"script_type": "Scheduler Event", "event_frequency": "Hourly"},
				lambda script: script.execute_scheduled_method(),
			),
			"Workflow Task": (
				{"script_type": "Workflow Task"},
				lambda script: script.execute_workflow_task(frappe.new_doc("ToDo")),
			),
			"Permission Query": (
				{"script_type": "Permission Query", "reference_doctype": "Note"},
				lambda script: script.get_permission_query_conditions("Administrator"),
			),
			"DocType Event": (
				{
					"script_type": "DocType Event",
					"reference_doctype": "ToDo",
					"doctype_event": "Before Insert",
				},
				lambda script: script.execute_doc(frappe.new_doc("ToDo")),
			),
		}
		for index, (script_type, (fields, run)) in enumerate(cases.items()):
			with self.subTest(script_type=script_type):
				script = self.make_file_script(f"test_file_loud_{index}", "", **fields)
				self.write_file_script(script, "def broken(:\n")
				with self.assertRaises(frappe.ValidationError):
					run(script)

				os.remove(script.get_file_path())
				with self.assertRaises(frappe.DoesNotExistError):
					run(script)

	def test_file_script_reads_environment_variables(self):
		script = self.make_file_script(
			"test_file_env",
			"frappe.flags = frappe.env.API_TOKEN\n",
			script_type="API",
			api_method="test_file_env",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		)

		with self.set_user("test@example.com"):
			self.assertEqual(frappe.get_doc("Server Script", script.name).execute_method(), "s3cr3t")

		self.write_file_script(script, "frappe.flags = frappe.env.MISSING\n")
		with self.set_user("test@example.com"):
			self.assertRaisesRegex(frappe.ValidationError, "MISSING", script.execute_method)

	def test_file_script_cannot_read_variable_values_directly(self):
		owner = self.make_file_script(
			"test_file_env_owner",
			"pass\n",
			script_type="API",
			api_method="test_file_env_owner",
			variables=[{"key": "API_TOKEN", "value": "s3cr3t"}],
		)
		reader = self.make_file_script(
			"test_file_env_reader",
			f'frappe.flags = frappe.get_doc("Server Script Variable", "{owner.variables[0].name}").get_password("value")\n',
			script_type="API",
			api_method="test_file_env_reader",
		)

		with self.set_user("test@example.com"):
			self.assertRaises(frappe.PermissionError, reader.execute_method)
