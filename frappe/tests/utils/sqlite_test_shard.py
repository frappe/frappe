import argparse
import importlib
import multiprocessing
import os
import subprocess
from pathlib import Path

import frappe
from frappe.commands.testing import main as run_tests


def restore_site(snapshot: Path, site_path: Path) -> None:
	subprocess.run(
		["rsync", "--archive", "--delete", f"{snapshot}/", f"{site_path}/"],
		check=True,
	)


def preload_modules(site: str, modules: list[str]) -> None:
	frappe.init(site)
	try:
		for module in modules:
			try:
				importlib.import_module(module)
			except Exception:
				# Imports that need a connected site still run normally in their child process.
				continue
	finally:
		frappe.destroy()
		if invalidator_thread := getattr(frappe.client_cache, "invalidator_thread", None):
			invalidator_thread.stop()
			invalidator_thread.join()
		frappe.cache = None
		frappe.client_cache = None


def run_module(site: str, app: str, module: str) -> None:
	try:
		frappe.init(site)
		run_tests(site=site, app=app, module=module)
	finally:
		frappe.destroy()


def run_modules(site: str, app: str, modules: list[str], snapshot: Path, site_path: Path) -> list[str]:
	failed_modules = []
	process_context = multiprocessing.get_context("fork")

	for module in modules:
		restore_site(snapshot, site_path)
		print(f"Running {module}", flush=True)
		process = process_context.Process(target=run_module, args=(site, app, module))
		process.start()
		process.join()
		if process.exitcode:
			failed_modules.append(module)

	return failed_modules


def main() -> None:
	parser = argparse.ArgumentParser(description="Run isolated SQLite test modules from a preloaded process")
	parser.add_argument("--site", required=True)
	parser.add_argument("--app", default="frappe")
	parser.add_argument("--modules-file", required=True, type=Path)
	parser.add_argument("--snapshot", required=True, type=Path)
	parser.add_argument("--sites-path", default=Path("sites"), type=Path)
	args = parser.parse_args()

	modules = [
		module for line in args.modules_file.resolve().read_text().splitlines() if (module := line.strip())
	]
	snapshot = args.snapshot.resolve()
	sites_path = args.sites_path.resolve()
	site_path = sites_path / args.site

	os.chdir(sites_path)
	restore_site(snapshot, site_path)
	preload_modules(args.site, modules)
	failed_modules = run_modules(args.site, args.app, modules, snapshot, site_path)
	if failed_modules:
		print("Failed modules:", flush=True)
		for module in failed_modules:
			print(f"  {module}", flush=True)
		raise SystemExit(1)


if __name__ == "__main__":
	main()
