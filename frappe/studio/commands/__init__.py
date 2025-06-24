import click
import frappe
from frappe.commands import get_site, pass_context


@click.command("build-studio-app")
@click.argument("app_name")
@click.option("--site", help="site name")
@pass_context
def build_studio_app(context, app_name: str, site: str | None = None):
	"""Build the studio app"""
	from studio.studio.doctype.studio_app.studio_app import StudioApp

	if not site:
		site = get_site(context)

	frappe.init(site)
	frappe.connect()
	app = frappe.get_doc("Studio App", app_name)
	app.generate_app_build()
	print(f"Studio App '{app_name}' built successfully.")


commands = [
	build_studio_app,
]
