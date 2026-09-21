# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections.abc import Callable

import click
import frappe


@click.group("flow-server")
def flow_server():
	"""Manage the bench-local Flow server daemon."""


@flow_server.command("setup")
def setup():
	"""Provision every site that has Flow and start the daemon."""
	from flow.daemon import lifecycle

	_run_on_every_flow_site(_provision)
	lifecycle.restart()
	_run_on_every_flow_site(_sync_tools)
	click.secho(lifecycle.status(), fg="green")


@flow_server.command("start")
def start():
	"""Start the daemon unless it already answers."""
	from flow.daemon import lifecycle

	lifecycle.ensure_running()
	_run_on_every_flow_site(_sync_tools)
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
	_run_on_every_flow_site(_sync_tools)
	click.secho(lifecycle.status(), fg="green")


@flow_server.command("status")
def status():
	"""Show whether the daemon answers and which sites it serves."""
	from flow.daemon import lifecycle

	click.echo(lifecycle.status())


def _run_on_every_flow_site(step: Callable[[str], None]) -> None:
	"""Run `step` connected to every site that has Flow installed."""
	from frappe.utils import get_sites

	for site in get_sites():
		frappe.init(site)
		try:
			frappe.connect()
			if "flow" in frappe.get_installed_apps():
				step(site)
		finally:
			frappe.destroy()


def _provision(site: str) -> None:
	from flow.daemon import lifecycle

	lifecycle.provision_site()
	click.echo(f"provisioned {site}")


def _sync_tools(_site: str) -> None:
	"""Mirror the daemon's extension tools as Flow Tool rows on this site."""
	from flow.flow.doctype.flow_tool.flow_tool import sync_server_tools

	sync_server_tools()
	frappe.db.commit()


commands = [flow_server]
