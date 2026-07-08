import os
import subprocess
import sys
from pathlib import Path

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


@click.command(
	"compare-rust-microbenchmarks",
	context_settings={"ignore_unknown_options": True},
)
@click.option(
	"--filter",
	"benchmark_filter",
	default="qb",
	show_default=True,
	help="Substring filter for benchmarks to compare, for example qb, orm, or qb_render_select_star.",
)
@click.option(
	"--output-dir",
	default="/tmp/frappe-rust-microbenchmarks",
	show_default=True,
	help="Directory where baseline and Rust pyperf JSON files are written.",
)
@click.option(
	"--force",
	is_flag=True,
	help="Overwrite existing paired pyperf JSON files in the output directory.",
)
@click.argument("benchargs", nargs=-1, type=click.UNPROCESSED)
@pass_context
def compare_rust_microbenchmarks(ctx, benchmark_filter, output_dir, force, benchargs):
	import frappe
	from frappe.tests.microbenchmarks import run_benchmarks as benchmark_runner

	if not ctx.sites:
		raise SiteNotSpecifiedError
	if "-o" in benchargs or "--output" in benchargs:
		raise click.UsageError("Use --output-dir instead of passing pyperf -o/--output.")

	site = ctx.sites[0]
	output_path = Path(output_dir)
	output_path.mkdir(parents=True, exist_ok=True)
	file_prefix = benchmark_filter.replace("/", "_").replace(" ", "_")
	baseline_path = output_path / f"{file_prefix}-python.json"
	rust_path = output_path / f"{file_prefix}-rust.json"
	if force:
		baseline_path.unlink(missing_ok=True)
		rust_path.unlink(missing_ok=True)

	common_args = [
		sys.executable,
		benchmark_runner.__file__,
		"--site",
		site,
		"--filter",
		benchmark_filter,
		*benchargs,
	]

	frappe.init(site)
	frappe.cache.flushall()
	click.echo(f"Running Python baseline: {baseline_path}")
	subprocess.check_call([*common_args, "-o", str(baseline_path)])

	frappe.cache.flushall()
	click.echo(f"Running Rust-enabled benchmark: {rust_path}")
	rust_env = os.environ.copy()
	rust_env["FRAPPE_QUERY_BUILDER_RUST"] = "1"
	subprocess.check_call(
		[
			*common_args,
			"--inherit-environ",
			"FRAPPE_QUERY_BUILDER_RUST",
			"-o",
			str(rust_path),
		],
		env=rust_env,
	)

	click.echo("Comparing results:")
	subprocess.check_call([sys.executable, "-m", "pyperf", "compare_to", str(baseline_path), str(rust_path)])


commands = [run_benchmarks, compare_rust_microbenchmarks]
