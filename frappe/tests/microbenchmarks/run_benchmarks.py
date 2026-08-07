#!/bin/env python3

import inspect
import random
from types import FunctionType

import pyperf

import frappe
from frappe.tests.microbenchmarks import (
	bench_background_jobs,
	bench_database,
	bench_orm,
	bench_qb,
	bench_redis,
	bench_utils,
	bench_web_requests,
)
from frappe.tests.microbenchmarks.utils import (
	NanoBenchmark,
	get_app_last_commit_date,
	get_app_last_commit_ref,
)
from frappe.utils import cstr

BENCHMARK_PREFIX = "bench_"


def run_microbenchmarks():
	def update_cmd_line(cmd, args):
		# Pass our added arguments to workers
		cmd.extend(["--site", args.site])
		cmd.extend(["--filter", cstr(args.benchmark_filter)])

	metadata = get_global_metadata()
	runner = pyperf.Runner(add_cmdline_args=update_cmd_line, metadata=metadata)

	runner.argparser.add_argument(
		"--filter",
		dest="benchmark_filter",
		help="Apply a filter to selectively run benchmarks. This is a substring filter.",
	)
	runner.argparser.add_argument(
		"--site", dest="site", help="Frappe site to use for benchmark", required=True
	)

	args = runner.argparser.parse_args()
	benchmarks = discover_benchmarks(cstr(args.benchmark_filter))
	setup(args.site)
	default_globals = {"frappe": frappe}
	for name, bench in benchmarks:
		if isinstance(bench, FunctionType):
			runner.bench_func(name, bench)
		elif isinstance(bench, NanoBenchmark):
			bench_globals = default_globals.copy()
			bench_globals.update(bench.globals or {})
			runner.timeit(
				name,
				stmt=bench.statement,
				setup=bench.setup,
				teardown=bench.teardown,
				globals=bench_globals,
			)
		else:
			raise ValueError("Unknown benchmark type:", type(bench))
	teardown(args.site)


def get_global_metadata() -> dict[str, str]:
	return {
		"frappe_commit": get_app_last_commit_ref("frappe"),
		"frappe_commit_date": get_app_last_commit_date("frappe"),
	}


def setup(site):
	frappe.init(site)
	assert frappe.conf.allow_tests
	frappe.connect()
	frappe.db.connect()
	random.seed(42)  # Ensure consistent results


def teardown(site):
	frappe.destroy()


def discover_benchmarks(benchmark_filter):
	benchmark_modules = [
		bench_orm,
		bench_database,
		bench_redis,
		bench_background_jobs,
		bench_web_requests,
		bench_utils,
		bench_qb,
	]

	all_benchmarks = set()
	benchmarks = []
	for module in benchmark_modules:
		module_name = module.__name__.split(".")[-1].removeprefix(BENCHMARK_PREFIX)
		for bench_name, bench in inspect.getmembers(
			module, predicate=lambda x: isinstance(x, FunctionType | NanoBenchmark)
		):
			if bench_name.startswith(BENCHMARK_PREFIX):
				bench_name = module_name + "_" + bench_name.removeprefix(BENCHMARK_PREFIX)
				if bench_name in all_benchmarks:
					frappe.throw(
						f"Another benchmark with same name exists: `{bench_name}`. Please rename the benchmark."
					)
				all_benchmarks.add(bench_name)
				if benchmark_filter in bench_name:
					benchmarks.append((bench_name, bench))

	return sorted(benchmarks, key=lambda x: x[0])


if __name__ == "__main__":
	run_microbenchmarks()
