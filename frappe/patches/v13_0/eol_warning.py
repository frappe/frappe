import click


def execute():
	click.secho(
		"Version 13 of Frappe Framework is no longer supported.\n"
		"Consider upgrading to latest version to recieve regular fixes and new features.",
		fg="red",
	)
