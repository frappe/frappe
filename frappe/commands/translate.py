import click

from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command("generate-pot", help="Generate gettext POT file")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def generate_pot(context, app: str):
	from frappe.translate import generate_pot

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	generate_pot(app)


@click.command("compile-translation", help="Compile PO files to MO files")
@click.option("--app", help="App name. eg: frappe")
@click.option("--locale", help="Compile transaltions only for this locale. eg: de")
@pass_context
def compile_translation(context, app: str = None, locale: str = None):
	from frappe.translate import compile

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	compile(app, locale)


@click.command("migrate-translation", help="Migrate CSV translation files to PO")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def migrate_translation(context, app: str):
	from frappe.translate import migrate

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	migrate(app)


@click.command("update-po", help="Sync PO files with main POT file")
@click.option("--app", help="App name. eg: frappe")
@pass_context
def update_po(context, app: str):
	from frappe.translate import update_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	update_po(app)


@click.command("new-po", help="Create PO file for lang code")
@click.argument("lang_code")
@click.option("--app", help="App name eg. frappe")
@pass_context
def new_po(context, lang_code: str, app: str):
	"""
	Create PO file for lang code
	"""
	from frappe.translate import new_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	new_po(lang_code, app)


def connect_to_site(site):
	from frappe import connect

	if not site:
		raise SiteNotSpecifiedError

	connect(site=site)


commands = [
	compile_translation,
	generate_pot,
	migrate_translation,
	new_po,
	update_po,
]
