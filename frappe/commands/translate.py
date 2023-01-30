import click

from frappe.commands import get_site, pass_context


@click.command("import-translations")
@click.argument("lang")
@click.argument("path")
@pass_context
def import_translations(context, lang, path):
	"Update translated strings"
	import frappe.translate

	site = get_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.translate.import_translations(lang, path)
	finally:
		frappe.destroy()


@click.command("generate-pot", help="Generate gettext POT file")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def generate_pot(context, app: str):
	import frappe
	from frappe.translate import generate_pot

	if not app:
		if not context["sites"]:
			raise Exception("--site is required")
		frappe.connect(site=context["sites"][0])

	generate_pot(app)


@click.command("compile-translation", help="Compile PO files to MO files")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def compile_translation(context, app: str):
	import frappe
	from frappe.translate import compile

	if not app:
		if not context["sites"]:
			raise Exception("--site is required")
		frappe.connect(site=context["sites"][0])

	compile(app)


@click.command("migrate-translation", help="Migrate CSV translation files to PO")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def migrate_translation(context, app: str):
	import frappe
	from frappe.translate import migrate

	if not app:
		if not context["sites"]:
			raise Exception("--site is required")
		frappe.connect(site=context["sites"][0])

	migrate(app)


@click.command("update-po", help="Sync PO files with main POT file")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def update_po(context, app: str):
	import frappe
	from frappe.translate import update_po

	if not app:
		if not context["sites"]:
			raise Exception("--site is required")
		frappe.connect(site=context["sites"][0])

	update_po(app)


@click.command("new-po", help="Create PO file for lang code")
@click.argument("lang_code")
@click.option("--app", help="App name eg. frappe")
@pass_context
def new_po(context, lang_code: str, app: str):
	"""
	Create PO file for lang code
	"""
	import frappe
	from frappe.translate import new_po

	if not app:
		if not context["sites"]:
			raise Exception("--site is required")
		frappe.connect(site=context["sites"][0])

	new_po(lang_code, app)


commands = [
	build_message_files,
	compile_translation,
	generate_pot,
	get_untranslated,
	import_translations,
	migrate_translation,
	new_language,
	new_po,
	update_po,
	update_translations,
]
