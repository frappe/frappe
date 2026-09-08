# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import click
import frappe


@click.group("flow-server")
def flow_server():
	"""Manage the bench-local Flow server daemon."""


@flow_server.command("setup")
def setup():
	"""Provision every site that has Flow and start the daemon."""
	from frappe.utils import get_sites

	from flow.daemon import lifecycle

	for site in get_sites():
		frappe.init(site)
		try:
			frappe.connect()
			if "flow" in frappe.get_installed_apps():
				lifecycle.provision_site()
				click.echo(f"provisioned {site}")
		finally:
			frappe.destroy()
	lifecycle.restart()
	click.secho(lifecycle.status(), fg="green")


@flow_server.command("start")
def start():
	"""Start the daemon unless it already answers."""
	from flow.daemon import lifecycle

	lifecycle.ensure_running()
	click.secho(lifecycle.status(), fg="green")


@flow_server.command("stop")
def stop():
	"""Stop the daemon."""
	from flow.daemon import lifecycle

	lifecycle.stop()
	click.echo(lifecycle.status())


@flow_server.command("restart")
def restart():
	"""Restart the daemon."""
	from flow.daemon import lifecycle

	lifecycle.restart()
	click.secho(lifecycle.status(), fg="green")


@flow_server.command("status")
def status():
	"""Show whether the daemon answers and which sites it serves."""
	from flow.daemon import lifecycle

	click.echo(lifecycle.status())


commands = [flow_server]
