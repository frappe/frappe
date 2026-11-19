import click

import frappe
from frappe.commands import get_site, pass_context
from frappe.utils.bench_helper import CliCtxObj


@click.command("settings-sidebar")
@click.argument("prefix", required=False)
@click.option("--json", "output_json", is_flag=True, help="Print the resolver's output as JSON")
@click.option("--user", help="Show the sidebar as this user sees it")
@click.option("--write", is_flag=True, help="Rewrite the app's settings_dialog/sidebar.txt for PREFIX")
@pass_context
def settings_sidebar(context: CliCtxObj, prefix=None, output_json=False, user=None, write=False):
	"Print the settings dialog's sidebar of a desk (every desk without PREFIX), or rewrite its sidebar.txt"
	from .settings_sidebar_text import describe_sidebars, write_settings_sidebar

	if write and not prefix:
		raise click.UsageError("--write needs a PREFIX.")

	site = get_site(context)
	with frappe.init_site(site):
		frappe.connect()
		try:
			if write:
				print(f"Wrote {write_settings_sidebar(prefix)}")
			else:
				print(describe_sidebars(prefix, as_json=output_json, user=user))
		except ValueError as error:
			raise click.ClickException(str(error)) from None
		finally:
			frappe.destroy()


commands = [settings_sidebar]
