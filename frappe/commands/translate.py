import click

from frappe.commands import profile, with_each_site, with_site
from frappe.exceptions import SiteNotSpecifiedError


# translation
@click.command("build-message-files")
@profile
@with_each_site()
def build_message_files(site, context):
	"Build message files for translation"
	import frappe.translate

	frappe.connect()
	frappe.translate.rebuild_all_translation_files()


@click.command("new-language")  # , help="Create lang-code.csv for given app")
@click.argument("lang_code")  # , help="Language code eg. en")
@click.argument("app")  # , help="App name eg. frappe")
@profile
@with_site
def new_language(site, context, lang_code, app):
	"""Create lang-code.csv for given app"""
	import frappe.translate

	frappe.connect()
	frappe.translate.write_translations_file(app, lang_code)

	print(
		"File created at ./apps/{app}/{app}/translations/{lang_code}.csv".format(
			app=app, lang_code=lang_code
		)
	)
	print(
		"You will need to add the language in frappe/geo/languages.json, if you haven't done it already."
	)


@click.command("get-untranslated")
@click.option("--app", default="_ALL_APPS")
@click.argument("lang")
@click.argument("untranslated_file")
@click.option("--all", default=False, is_flag=True, help="Get all message strings")
@profile
@with_site
def get_untranslated(site, context, lang, untranslated_file, app="_ALL_APPS", all=None):
	"Get untranslated strings for language"
	import frappe.translate

	frappe.connect()
	frappe.translate.get_untranslated(lang, untranslated_file, get_all=all, app=app)


@click.command("update-translations")
@click.option("--app", default="_ALL_APPS")
@click.argument("lang")
@click.argument("untranslated_file")
@click.argument("translated-file")
@profile
@with_site
def update_translations(site, context, lang, untranslated_file, translated_file, app="_ALL_APPS"):
	"Update translated strings"
	import frappe.translate

	frappe.connect()
	frappe.translate.update_translations(lang, untranslated_file, translated_file, app=app)


@click.command("import-translations")
@click.argument("lang")
@click.argument("path")
@profile
@with_site
def import_translations(site, context, lang, path):
	"Update translated strings"
	import frappe.translate

	frappe.connect()
	frappe.translate.import_translations(lang, path)


@click.command("migrate-translations")
@click.argument("source-app")
@click.argument("target-app")
@profile
@with_site
def migrate_translations(site, context, source_app, target_app):
	"Migrate target-app-specific translations from source-app to target-app"
	import frappe.translate

	frappe.connect()
	frappe.translate.migrate_translations(source_app, target_app)


commands = [
	build_message_files,
	get_untranslated,
	import_translations,
	new_language,
	update_translations,
	migrate_translations,
]
