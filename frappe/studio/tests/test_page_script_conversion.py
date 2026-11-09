import frappe
from frappe.studio import files
from frappe.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from frappe.studio.doctype.studio_page.patches.convert_page_scripts_to_modules import (
	execute,
	get_top_level_bindings,
	is_module,
	move_router_script_to_file,
	to_setup_module,
	tokenize,
)
from frappe.tests import IntegrationTestCase


def bindings(source: str) -> list[str]:
	return get_top_level_bindings(list(tokenize(source)))


class TestPageScriptConversion(IntegrationTestCase):
	def test_finds_top_level_bindings(self):
		self.assertEqual(bindings("const a = 1\nlet b, c\nvar d = 2\n"), ["a", "b", "c", "d"])
		self.assertEqual(
			bindings("function one() {}\nclass Two {}\nasync function three() {}"), ["one", "Two", "three"]
		)
		self.assertEqual(bindings("const { a: renamed, b = 5, ...rest } = payload"), ["renamed", "b", "rest"])
		self.assertEqual(bindings("const [first, , second] = items"), ["first", "second"])
		self.assertEqual(bindings("const { y } = obj, z = 3"), ["y", "z"])

	def test_ignores_declarations_that_are_not_top_level(self):
		self.assertEqual(bindings("if (x) { const hidden = 1 }\nconst shown = 2"), ["shown"])
		self.assertEqual(bindings("for (const item of items) {}\nconst total = 1"), ["total"])
		self.assertEqual(
			bindings("const fn = function named() {}\nconst cls = class Named {}"), ["fn", "cls"]
		)

	def test_reads_past_strings_comments_and_regexes(self):
		self.assertEqual(bindings('const re = /\\{"[a-z]+\\/{2}/g\nconst after = 1'), ["re", "after"])
		self.assertEqual(bindings("const t = `a ${ `b ${deep}` } c`\nconst tail = 1"), ["t", "tail"])
		self.assertEqual(bindings("const a = 1 // const b = 2\n/* const c = 3 */\nconst d = 4"), ["a", "d"])
		self.assertEqual(bindings("const s = 'it\\'s, {a}'\nconst u = 1"), ["s", "u"])

	def test_converts_a_script_to_a_setup_module(self):
		source = (
			"const count = ref(0)\n"
			"const rows = computed(() => todos.data || [])\n"
			"function increment() { count.value++ }\n"
		)
		module = to_setup_module(source, ["todos", "route", "router"])
		self.assertIn('import { ref, computed } from "vue"', module)
		self.assertIn("const { todos } = context", module)
		self.assertIn("export default function setup(context) {", module)
		self.assertIn("\tconst count = ref(0)", module)
		self.assertIn("return { count, rows, increment }", module)
		self.assertNotIn("route", module.split("export default")[0])

	def test_imports_each_api_from_the_module_that_exports_it(self):
		module = to_setup_module("watchDebounced(() => x, () => toast.success('hi'))\n", [])
		self.assertIn('import { watchDebounced } from "@vueuse/core"', module)
		self.assertIn('import { toast } from "frappe-ui"', module)

	def test_a_declaration_shadows_what_the_context_offered(self):
		module = to_setup_module("const filter = ref('')\n", ["filter", "route"])
		self.assertNotIn("= context", module)
		self.assertIn("return { filter }", module)

	def test_a_template_literal_keeps_its_own_indentation(self):
		module = to_setup_module("const html = `<p>\nhello\n</p>`\n", [])
		self.assertIn("\tconst html = `<p>\nhello\n</p>`", module)

	def test_recognises_an_already_converted_script(self):
		self.assertFalse(is_module("const a = 1\n"))
		self.assertTrue(is_module(to_setup_module("const a = 1\n", [])))
		self.assertFalse(is_module("const a = 'export default x'\n"))

	def test_patch_converts_database_pages_and_the_router_script(self):
		app = make_studio_app(app_name="converted-app", app_title="Converted App")
		page = make_studio_page(app.name, page_title="Board", script="const count = ref(0)\n")

		execute()

		converted = frappe.db.get_value("Studio Page", page.name, "script")
		self.assertIn('import { ref } from "vue"', converted)
		self.assertIn("return { count }", converted)

		# The app no longer has a router_script column, so move its value directly.
		move_router_script_to_file(app.name, "{ setup(router) {} }")
		self.assertEqual(
			files.read_store_file(app.name, "router.js"), "export default { setup(router) {} }\n"
		)

		execute()
		self.assertEqual(frappe.db.get_value("Studio Page", page.name, "script"), converted)
