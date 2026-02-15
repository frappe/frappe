# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
Bench command to generate OpenAPI specification.
Usage: bench generate-openapi-spec
"""

import click

import frappe
from frappe.commands import get_site, pass_context
from frappe.core.openapi.generator import generate_specification


@click.command("generate-openapi-spec")
@pass_context
@click.option("--clear-cache", "clear_cache", is_flag=True, help="Clear cached spec")
def generate_openapi_spec(context, clear_cache):
    """Generate OpenAPI specification for site."""

    site = get_site(context)
    frappe.init(site=site)
    frappe.connect()

    try:
        frappe.init(site)
        frappe.connect()

        if clear_cache:
            cache_key = f"openapi_spec:{site}"
            frappe.cache().delete_value(cache_key)
            click.echo(f"Cleared cache for {site}")

        click.echo(f"Generating OpenAPI specification for {site}...")

        spec = generate_specification(site)

        click.echo(
            click.style(
                f"OpenAPI specification generated successfully!",
                fg="green",
                bold=True,
            )
        )
        click.echo(f"Paths: {len(spec.get('paths', {}))} endpoints")
        click.echo(
            f"Schemas: {len(spec.get('components', {}).get('schemas', {}))} models"
        )
        click.echo("")

        frappe.destroy()

    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red", bold=True), err=True)
        frappe.destroy()
        raise click.Abort()
