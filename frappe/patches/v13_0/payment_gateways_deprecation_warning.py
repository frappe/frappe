import click


def execute():
	click.secho(
		"Payment Gateways are moved to a separate app in version 14.\n"
		"When upgrading to Frappe version-14, Please install the 'Payments' app to continue using them: https://github.com/frappe/payments",
		fg="yellow",
	)
