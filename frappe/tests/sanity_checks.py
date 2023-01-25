from pathlib import Path

import click

import frappe
from frappe.modules import patch_handler
from frappe.utils import get_bench_path


def run_sanity_checks(app: str):
	_check_patches_exist(app)


def _check_patches_exist(app):
	"""Make sure all patches/**.py files are part of patches.txt"""

	patch_dir = Path(frappe.get_app_path(app))

	app_patches = [p.split(maxsplit=1)[0] for p in patch_handler.get_patches_from_app(app)]

	missing_patches = []

	for file in patch_dir.glob("**/patches/**/*.py"):
		module = _get_dotted_path(file, app)
		try:
			patch_module = frappe.get_module(module)
			if hasattr(patch_module, "execute"):
				if module not in app_patches:
					missing_patches.append(module)
		except Exception:
			# patch so bad it doesn't even import :shrug:
			missing_patches.append(module)

	if missing_patches:
		click.echo("Patches missing in patch.txt: \n" + "\n".join(missing_patches))
		raise SystemExit(1)


def _get_dotted_path(file: Path, app) -> str:
	app_path = Path(get_bench_path()) / "apps" / app

	*path, filename = file.relative_to(app_path).parts
	base_filename = Path(filename).stem

	return ".".join(path + [base_filename])
