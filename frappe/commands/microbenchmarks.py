import subprocess
import sys

import click

from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command(
	"run-microbenchmarks",
	context_settings={"ignore_unknown_options": True},
	add_help_option=False,
)
@click.argument("benchargs", nargs=-1, type=click.UNPROCESSED)
@pass_context
def run_benchmarks(ctx, benchargs):
	import frappe
	from frappe.tests.microbenchmarks import run_benchmarks as benchmark_runner

	if not ctx.sites:
		raise SiteNotSpecifiedError

	site = ctx.sites[0]
	benchargs = ("--site", site, *benchargs)

	frappe.init(site)
	frappe.cache.flushall()

	# pyperf expects the benchmark script to be the process entry point.
	subprocess.check_call([sys.executable, benchmark_runner.__file__, *benchargs])


commands = [run_benchmarks]
