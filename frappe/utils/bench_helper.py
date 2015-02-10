import click
import frappe
import importlib

def main():
	click.Group(commands=get_app_groups())()

def get_cli_options():
	pass

def get_app_groups():
	ret = {}
	for app in get_apps():
		app_group = get_app_group(app)
		if app_group:
			ret[app] = app_group
	return ret

def get_app_group(app):
	app_commands = get_app_commands(app)
	if app_commands:
		return click.Group(name=app, commands=app_commands)

def get_app_commands(app):
	try:
		app_command_module = importlib.import_module(app + '.commands')
	except ImportError:
		return []
	
	ret = {}
	for command in getattr(app_command_module, 'commands', []):
		ret[command.name] = command
	return ret

def get_apps():
	return frappe.get_all_apps(with_internal_apps=False, sites_path='.')

if __name__ == "__main__":
	main()

