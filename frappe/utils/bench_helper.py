from __future__ import unicode_literals, print_function
import click
import frappe
import os
import json
import importlib
import frappe.utils
import traceback

click.disable_unicode_literals_warning = True

def main():
	commands = get_app_groups()
	commands.update({
		'get-frappe-commands': get_frappe_commands,
		'get-frappe-help': get_frappe_help
	})
	click.Group(commands=commands)(prog_name='bench')

def get_app_groups():
	'''Get all app groups, put them in main group "frappe" since bench is
	designed to only handle that'''
	commands = dict()
	for app in get_apps():
		app_commands = get_app_commands(app)
		if app_commands:
			commands.update(app_commands)

	ret = dict(frappe=click.group(name='frappe', commands=commands)(app_group))
	return ret

def get_app_group(app):
	app_commands = get_app_commands(app)
	if app_commands:
		return click.group(name=app, commands=app_commands)(app_group)

@click.option('--site')
@click.option('--profile', is_flag=True, default=False, help='Profile')
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
@click.option('--force', is_flag=True, default=False, help='Force')
@click.pass_context
def app_group(ctx, site=False, force=False, verbose=False, profile=False):
	ctx.obj = {
		'sites': get_sites(site),
		'force': force,
		'verbose': verbose,
		'profile': profile
	}
	if ctx.info_name == 'frappe':
		ctx.info_name = ''

def get_sites(site_arg):
	if site_arg == 'all':
		return frappe.utils.get_sites()
	elif site_arg:
		return [site_arg]
	elif os.path.exists('currentsite.txt'):
		with open('currentsite.txt') as f:
			site = f.read().strip()
			if site:
				return [site]
	return []

def get_app_commands(app):
	if os.path.exists(os.path.join('..', 'apps', app, app, 'commands.py'))\
		or os.path.exists(os.path.join('..', 'apps', app, app, 'commands', '__init__.py')):
		try:
			app_command_module = importlib.import_module(app + '.commands')
		except Exception:
			traceback.print_exc()
			return []
	else:
		return []

	ret = {}
	for command in getattr(app_command_module, 'commands', []):
		ret[command.name] = command
	return ret

@click.command('get-frappe-commands')
def get_frappe_commands():
	commands = list(get_app_commands('frappe'))

	for app in get_apps():
		app_commands = get_app_commands(app)
		if app_commands:
			commands.extend(list(app_commands))

	print(json.dumps(commands))

@click.command('get-frappe-help')
def get_frappe_help():
	print(click.Context(get_app_groups()['frappe']).get_help())

def get_apps():
	return frappe.get_all_apps(with_internal_apps=False, sites_path='.')

if __name__ == "__main__":
	main()

