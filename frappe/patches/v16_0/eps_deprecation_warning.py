import click

import frappe


def execute():
	click.secho(
		"Social Module/Energy Points System is moved to a separate app and will be removed from ERPNext in version-16.\n"
		"Please install the app to continue using the integration: https://github.com/frappe/eps",
		fg="yellow",
	)
