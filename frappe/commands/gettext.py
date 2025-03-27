import click

from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils.bench_helper import CliCtxObj


@click.command("generate-pot-file", help="Translation: generate POT file")
@click.option("--app", help="Only generate for this app. eg: frappe")
@pass_context
def generate_pot_file(context: CliCtxObj, app: str | None = None):
	from frappe.gettext.translate import generate_pot

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	generate_pot(app)


@click.command("compile-po-to-mo", help="Translation: compile PO files to MO files")
@click.option("--app", help="Only compile for this app. eg: frappe")
@click.option(
	"--force",
	is_flag=True,
	default=False,
	help="Force compile even if there are no changes to PO files",
)
@click.option("--locale", help="Compile transaltions only for this locale. eg: de")
@pass_context
def compile_translations(context: CliCtxObj, app: str | None = None, locale: str | None = None, force=False):
	from frappe.gettext.translate import compile_translations as _compile_translations

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	_compile_translations(app, locale, force=force)


@click.command("migrate-csv-to-po", help="Translation: migrate from CSV files (old) to PO files (new)")
@click.option("--app", help="Only migrate for this app. eg: frappe")
@click.option("--locale", help="Compile translations only for this locale. eg: de")
@pass_context
def csv_to_po(context: CliCtxObj, app: str | None = None, locale: str | None = None):
	from frappe.gettext.translate import migrate

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	migrate(app, locale)


@click.command(
	"update-po-files",
	help="""Translation: sync PO files with POT file.
You might want to run generate-pot-file first.""",
)
@click.option("--app", help="Only update for this app. eg: frappe")
@click.option("--locale", help="Update PO files only for this locale. eg: de")
@pass_context
def update_po_files(context: CliCtxObj, app: str | None = None, locale: str | None = None):
	from frappe.gettext.translate import update_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	update_po(app, locale=locale)


@click.command("create-po-file", help="Translation: create a new PO file for a locale")
@click.argument("locale", nargs=1)
@click.option("--app", help="Only create for this app. eg: frappe")
@pass_context
def create_po_file(context: CliCtxObj, locale: str, app: str | None = None):
	"""Create PO file for lang code"""
	from frappe.gettext.translate import new_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	new_po(locale, app)


def connect_to_site(site):
	from frappe import connect

	if not site:
		raise SiteNotSpecifiedError

	connect(site=site)


commands = [
	generate_pot_file,
	compile_translations,
	csv_to_po,
	update_po_files,
	create_po_file,
]
