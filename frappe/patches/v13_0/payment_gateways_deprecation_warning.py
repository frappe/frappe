import click


def execute():
	click.secho(
		"Payment Gateways are moved to a separate app in version 14.\n"
		"Please install the app to continue using them: https://github.com/frappe/payments",
		fg="yellow",
	)
