import click

from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command("generate-pot-file", help="Translation: generate POT file")
@click.option("--app", help="Only generate for this app. eg: frappe")
@pass_context
def generate_pot_file(context, app: str | None = None):
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
def compile_translations(context, app: str | None = None, locale: str | None = None, force=False):
	from frappe.gettext.translate import compile_translations as _compile_translations

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	_compile_translations(app, locale, force=force)


@click.command("migrate-csv-to-po", help="Translation: migrate from CSV files (old) to PO files (new)")
@click.option("--app", help="Only migrate for this app. eg: frappe")
@click.option("--locale", help="Compile translations only for this locale. eg: de")
@pass_context
def csv_to_po(context, app: str | None = None, locale: str | None = None):
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
def update_po_files(context, app: str | None = None, locale: str | None = None):
	from frappe.gettext.translate import update_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	update_po(app, locale=locale)


@click.command("create-po-file", help="Translation: create a new PO file for a locale")
@click.argument("locale", nargs=1)
@click.option("--app", help="Only create for this app. eg: frappe")
@pass_context
def create_po_file(context, locale: str, app: str | None = None):
	"""Create PO file for lang code"""
	from frappe.gettext.translate import new_po

	if not app:
		connect_to_site(context.sites[0] if context.sites else None)

	new_po(locale, app)


@click.command("update-csv-from-po")
@click.argument("app", nargs=1)
@click.option("--locale", help="Update CSV file only for this locale. eg: de")
def update_csv_from_po(app: str, locale: str | None = None) -> None:
	"""Add missing translations from PO file to CSV file.

	How to:
	(1) add a [locale].po file in the app's `locale` directory (this can be downloaded from the new translation platform or copied from another branch), then
	(2) run this command.

	This will add all translations to the CSV file, that are in the PO file but were missing in the CSV file.

	This command is intended for backporting translations from the new translation system to the old one.
	"""
	from frappe.gettext.translate import update_csv_from_po

	update_csv_from_po(app, locale)


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
	update_csv_from_po,
]
