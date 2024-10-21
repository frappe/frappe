import importlib
import json
import linecache
import os
import sys
import traceback
import warnings
from dataclasses import dataclass
from textwrap import dedent

import click

import frappe
import frappe.utils

click.disable_unicode_literals_warning = True


def FrappeClickWrapper(cls, handler):
	class Cls(cls):
		# only implemented on groups
		def get_command(self, ctx, cmd_name):
			rv = super().get_command(ctx, cmd_name)
			if rv is not None:
				return rv

			all_commands = self.list_commands(ctx)
			from difflib import get_close_matches

			possibilities = get_close_matches(cmd_name, all_commands)
			raise click.NoSuchOption(
				cmd_name, possibilities=possibilities, message=f"No such command: {cmd_name}."
			)

		def make_context(self, info_name, args, parent=None, **extra):
			try:
				return super().make_context(info_name, args, parent=parent, **extra)
			except (click.ClickException, click.exceptions.Exit, click.exceptions.Abort) as e:
				raise e
			except Exception as exc:
				# call the handler
				handler(self, info_name, exc)
				sys.exit(1)

		def invoke(self, ctx):
			try:
				return super().invoke(ctx)
			except (click.ClickException, click.exceptions.Exit, click.exceptions.Abort) as e:
				raise e
			except Exception as exc:
				# call the handler
				handler(self, ctx.info_name, exc)
				sys.exit(1)

	return Cls


# for type hints
@dataclass
class CliCtxObj:
	sites: list[str]
	force: bool
	profile: bool
	verbose: bool


def handle_exception(cmd, info_name, exc):
	tb = sys.exc_info()[2]
	while tb.tb_next:
		tb = tb.tb_next
	frame = tb.tb_frame
	filename = frame.f_code.co_filename
	lineno = frame.f_lineno

	click.secho("\n:: ", nl=False)
	click.secho(f"{exc}", fg="red", bold=True, nl=False)
	click.secho(" ::")
	click.secho("\nContext:", fg="yellow", bold=True)
	click.secho(f" File '{filename}', line {lineno}\n")
	context_lines = 5
	start = max(1, lineno - context_lines)
	end = lineno + context_lines + 1

	for i in range(start, end):
		line = linecache.getline(filename, i).rstrip()
		if i == lineno:
			click.secho(f"{i:4d}> {line}", fg="red")
		else:
			click.echo(f"{i:4d}: {line}")

	show_exception = (not sys.stdout.isatty()) or click.confirm(
		"\nDo you want to see the full traceback?", default=False
	)
	if show_exception:
		click.secho("\nFull traceback:", fg="red")
		click.echo(traceback.format_exc())

		click.echo(exc)


def main():
	commands = get_app_groups()
	commands.update({"get-frappe-commands": get_frappe_commands, "get-frappe-help": get_frappe_help})
	FrappeClickWrapper(click.Group, handle_exception)(commands=commands)(prog_name="bench")


def get_app_groups() -> dict[str, click.Group | click.Command]:
	"""Get all app groups, put them in main group "frappe" since bench is
	designed to only handle that"""
	commands = {}
	for app in get_apps():
		if app_commands := get_app_commands(app):
			commands |= app_commands
	return dict(
		frappe=click.group(
			name="frappe", commands=commands, cls=FrappeClickWrapper(click.Group, handle_exception)
		)(app_group)
	)


def get_app_group(app: str) -> click.Group:
	if app_commands := get_app_commands(app):
		return click.group(
			name=app, commands=app_commands, cls=FrappeClickWrapper(click.Group, handle_exception)
		)(app_group)


@click.option("--site")
@click.option("--profile", is_flag=True, default=False, help="Profile")
@click.option("--verbose", is_flag=True, default=False, help="Verbose")
@click.option("--force", is_flag=True, default=False, help="Force")
@click.pass_context
def app_group(ctx, site=False, force=False, verbose=False, profile=False):
	ctx.obj = CliCtxObj(sites=get_sites(site), force=force, verbose=verbose, profile=profile)
	if ctx.info_name == "frappe":
		ctx.info_name = ""


def get_sites(site_arg: str) -> list[str]:
	if site_arg == "all":
		return frappe.utils.get_sites()
	elif site_arg:
		return [site_arg]
	elif env_site := os.environ.get("FRAPPE_SITE"):
		return [env_site]
	elif default_site := frappe.get_conf().default_site:
		return [default_site]
	# This is not supported, just added here for warning.
	elif (site := frappe.read_file("currentsite.txt")) and site.strip():
		click.secho(
			dedent(
				f"""
			WARNING: currentsite.txt is not supported anymore for setting default site. Use following command to set it as default site.
			$ bench use {site}"""
			),
			fg="red",
		)

	return []


def get_app_commands(app: str) -> dict:
	ret = {}
	try:
		app_command_module = importlib.import_module(f"{app}.commands")
	except ModuleNotFoundError as e:
		if e.name == f"{app}.commands":
			return ret
		traceback.print_exc()
		return ret
	except Exception:
		traceback.print_exc()
		return ret
	for command in getattr(app_command_module, "commands", []):
		ret[command.name] = command
	return ret


@click.command("get-frappe-commands")
def get_frappe_commands():
	commands = list(get_app_commands("frappe"))

	for app in get_apps():
		app_commands = get_app_commands(app)
		if app_commands:
			commands.extend(list(app_commands))

	print(json.dumps(commands))


@click.command("get-frappe-help")
def get_frappe_help():
	print(click.Context(get_app_groups()["frappe"]).get_help())


def get_apps():
	return frappe.get_all_apps(with_internal_apps=False, sites_path=".")


if __name__ == "__main__":
	if not frappe._dev_server:
		warnings.simplefilter("ignore")

	main()
