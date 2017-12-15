# Copyright (c) 2015, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import, print_function
import sys
import click
import cProfile
import pstats
import frappe
import frappe.utils
from functools import wraps
from six import StringIO

click.disable_unicode_literals_warning = True

def pass_context(f):
	@wraps(f)
	def _func(ctx, *args, **kwargs):
		profile = ctx.obj['profile']
		if profile:
			pr = cProfile.Profile()
			pr.enable()

		ret = f(frappe._dict(ctx.obj), *args, **kwargs)

		if profile:
			pr.disable()
			s = StringIO()
			ps = pstats.Stats(pr, stream=s)\
				.sort_stats('cumtime', 'tottime', 'ncalls')
			ps.print_stats()

			# print the top-100
			for line in s.getvalue().splitlines()[:100]:
				print(line)

		return ret

	return click.pass_context(_func)

def get_site(context):
	try:
		site = context.sites[0]
		return site
	except (IndexError, TypeError):
		print('Please specify --site sitename')
		sys.exit(1)

def call_command(cmd, context):
	return click.Context(cmd, obj=context).forward(cmd)

def get_commands():
	# prevent circular imports
	from .docs import commands as doc_commands
	from .scheduler import commands as scheduler_commands
	from .site import commands as site_commands
	from .translate import commands as translate_commands
	from .utils import commands as utils_commands

	return list(set(doc_commands + scheduler_commands + site_commands + translate_commands + utils_commands))

commands = get_commands()
