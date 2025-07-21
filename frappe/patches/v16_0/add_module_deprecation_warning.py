import click


def execute():
	module_app_map = {
		"Social Module/ Energy Points System": ("eps", "system"),
		"Offsite Backup Integrations (Google Drive, S3, Dropbox)": ("offsite_backups", "intergration"),
		"Newsletter": ("newsletter", "functionality"),
	}
	for module, (app, system_type) in module_app_map.items():
		click.secho(
			f"{module} is moving to a new app and will removed from the framework in version-16.\n"
			f"Please install the app to continue using the {system_type}: https://github.com/frappe/{app}",
			fg="yellow",
		)
		click.secho("\n")
