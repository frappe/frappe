# Copyright (c) 2015, Web Notes Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import cProfile
import pstats
import subprocess  # nosec
import sys
from functools import wraps
from io import StringIO
from os import environ

import click

import frappe
import frappe.utils

click.disable_unicode_literals_warning = True


def pass_context(f):
	@wraps(f)
	def _func(ctx, *args, **kwargs):
		profile = ctx.obj["profile"]
		if profile:
			pr = cProfile.Profile()
			pr.enable()

		try:
			ret = f(frappe._dict(ctx.obj), *args, **kwargs)
		except frappe.exceptions.SiteNotSpecifiedError as e:
			click.secho(str(e), fg="yellow")
			sys.exit(1)
		except frappe.exceptions.IncorrectSitePath:
			site = ctx.obj.get("sites", "")[0]
			click.secho(f"Site {site} does not exist!", fg="yellow")
			sys.exit(1)

		if profile:
			pr.disable()
			s = StringIO()
			ps = pstats.Stats(pr, stream=s).sort_stats("cumtime", "tottime", "ncalls")
			ps.print_stats()

			# print the top-100
			for line in s.getvalue().splitlines()[:100]:
				print(line)

		return ret

	return click.pass_context(_func)


def get_site(context, raise_err=True):
	try:
		site = context.sites[0]
		return site
	except (IndexError, TypeError):
		if raise_err:
			raise frappe.SiteNotSpecifiedError
		return None


def popen(command, *args, **kwargs):
	output = kwargs.get("output", True)
	cwd = kwargs.get("cwd")
	shell = kwargs.get("shell", True)
	raise_err = kwargs.get("raise_err")
	env = kwargs.get("env")
	if env:
		env = dict(environ, **env)

	def set_low_prio():
		import psutil

		if psutil.LINUX:
			psutil.Process().nice(19)
			psutil.Process().ionice(psutil.IOPRIO_CLASS_IDLE)
		elif psutil.WINDOWS:
			psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
			psutil.Process().ionice(psutil.IOPRIO_VERYLOW)
		else:
			psutil.Process().nice(19)
			# ionice not supported

	proc = subprocess.Popen(
		command,
		stdout=None if output else subprocess.PIPE,
		stderr=None if output else subprocess.PIPE,
		shell=shell,
		cwd=cwd,
		preexec_fn=set_low_prio,
		env=env,
	)

	return_ = proc.wait()

	if return_ and raise_err:
		raise subprocess.CalledProcessError(return_, command)

	return return_


def call_command(cmd, context):
	return click.Context(cmd, obj=context).forward(cmd)


def get_commands():
	# prevent circular imports
	from .redis_utils import commands as redis_commands
	from .scheduler import commands as scheduler_commands
	from .site import commands as site_commands
	from .translate import commands as translate_commands
	from .utils import commands as utils_commands

	clickable_link = "\x1b]8;;https://frappeframework.com/docs\afrappeframework.com\x1b]8;;\a"
	all_commands = (
		scheduler_commands + site_commands + translate_commands + utils_commands + redis_commands
	)

	for command in all_commands:
		if not command.help:
			command.help = f"Refer to {clickable_link}"

	return all_commands


commands = get_commands()
