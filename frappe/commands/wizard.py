# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import click

import frappe
from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils.bench_helper import CliCtxObj


@click.command("setup-wizard")
@click.option("--language", default="English", show_default=True, help="System language")
@click.option("--country", required=True, help="Country name (e.g. Australia)")
@click.option("--timezone", required=True, help="Timezone (e.g. Australia/Sydney)")
@click.option("--currency", required=True, help="Currency code (e.g. AUD)")
@click.option("--full-name", default="Administrator", show_default=True, help="Administrator full name")
@click.option("--email", default="admin@example.com", show_default=True, help="Administrator email")
@click.option("--password", default="admin", show_default=True, help="Administrator password")
@click.option("--company-name", default=None, help="Company name (ERPNext)")
@click.option("--company-abbr", default=None, help="Company abbreviation (ERPNext)")
@click.option(
	"--chart-of-accounts", default="Standard", show_default=True, help="Chart of accounts template (ERPNext)"
)
@click.option(
	"--background",
	is_flag=True,
	default=False,
	help="Fork to background and return immediately; progress is logged to stdout",
)
@pass_context
def setup_wizard(
	context: CliCtxObj,
	language,
	country,
	timezone,
	currency,
	full_name,
	email,
	password,
	company_name,
	company_abbr,
	chart_of_accounts,
	background,
):
	"Run the setup wizard for a site from the command line (no browser required)"
	import os

	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	args = {
		"language": language,
		"country": country,
		"timezone": timezone,
		"currency": currency,
		"full_name": full_name,
		"email": email,
		"password": password,
	}
	if company_name:
		args["company_name"] = company_name
	if company_abbr:
		args["company_abbr"] = company_abbr
	if chart_of_accounts:
		args["chart_of_accounts"] = chart_of_accounts

	for site in context.sites:
		if background:
			pid = os.fork()
			if pid > 0:
				click.echo(f"Setup wizard forked to background (PID {pid}). Follow logs for progress.")
				continue

		frappe.init(site=site)
		frappe.connect()
		try:
			if frappe.db.get_single_value("System Settings", "setup_complete"):
				click.echo(f"Site '{site}': setup already complete — skipping.")
				continue
			click.echo(f"Site '{site}': running setup wizard...")
			result = setup_complete(frappe._dict(args))
			if result and result.get("status") == "ok":
				click.echo(f"Site '{site}': setup complete ✓")
			else:
				click.echo(f"Site '{site}': setup failed — {result}", err=True)
				raise SystemExit(1)
		finally:
			frappe.destroy()

		if background:
			os._exit(0)

	if not context.sites:
		raise SiteNotSpecifiedError


commands = [setup_wizard]
