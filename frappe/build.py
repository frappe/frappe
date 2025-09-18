# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import re
import shutil
import subprocess
from contextlib import suppress
from subprocess import getoutput
from tempfile import mkdtemp
from urllib.parse import urlparse

import click
from semantic_version import Version

import frappe

timestamps = {}
app_paths = None
sites_path = os.path.abspath(os.getcwd())
WHITESPACE_PATTERN = re.compile(r"\s+")
HTML_COMMENT_PATTERN = re.compile(r"(<!--.*?-->)")


class AssetsNotDownloadedError(Exception):
	pass


class AssetsDontExistError(Exception):
	pass


def download_file(url, prefix):
	from requests import get

	filename = urlparse(url).path.split("/")[-1]
	local_filename = os.path.join(prefix, filename)
	with get(url, stream=True, allow_redirects=True) as r:
		r.raise_for_status()
		with open(local_filename, "wb") as f:
			for chunk in r.iter_content(chunk_size=8192):
				f.write(chunk)
	return local_filename


def build_missing_files():
	"""Check which files dont exist yet from the assets.json and run build for those files"""

	missing_assets = []
	current_asset_files = []

	for type in ["css", "js"]:
		folder = os.path.join(sites_path, "assets", "frappe", "dist", type)
		current_asset_files.extend(os.listdir(folder))

	development = frappe.local.conf.developer_mode or frappe._dev_server
	build_mode = "development" if development else "production"

	assets_json = frappe.read_file("assets/assets.json")
	if assets_json:
		assets_json = frappe.parse_json(assets_json)

		for bundle_file, output_file in assets_json.items():
			if not output_file.startswith("/assets/frappe"):
				continue

			if os.path.basename(output_file) not in current_asset_files:
				missing_assets.append(bundle_file)

		if missing_assets:
			click.secho("\nBuilding missing assets...\n", fg="yellow")
			files_to_build = ["frappe/" + name for name in missing_assets]
			bundle(build_mode, files=files_to_build)
	else:
		# no assets.json, run full build
		bundle(build_mode, apps="frappe")


def get_assets_link(frappe_head) -> str:
	import requests

	tag = getoutput(
		r"cd ../apps/frappe && git show-ref --tags -d | grep {} | sed -e 's,.*"
		r" refs/tags/,,' -e 's/\^{{}}//'".format(frappe_head)
	)

	if tag:
		# if tag exists, download assets from github release
		url = f"https://github.com/frappe/frappe/releases/download/{tag}/assets.tar.gz"
	else:
		url = f"http://assets.frappeframework.com/{frappe_head}.tar.gz"

	if not requests.head(url):
		reference = f"Release {tag}" if tag else f"Commit {frappe_head}"
		raise AssetsDontExistError(f"Assets for {reference} don't exist")

	return url


def fetch_assets(url, frappe_head):
	click.secho("Retrieving assets...", fg="yellow")

	prefix = mkdtemp(prefix="frappe-assets-", suffix=frappe_head)
	assets_archive = download_file(url, prefix)

	if not assets_archive:
		raise AssetsNotDownloadedError(f"Assets could not be retrived from {url}")

	click.echo(click.style("✔", fg="green") + f" Downloaded Frappe assets from {url}")

	return assets_archive


def setup_assets(assets_archive):
	import tarfile

	directories_created = set()

	click.secho("\nExtracting assets...\n", fg="yellow")
	with tarfile.open(assets_archive) as tar:
		for file in tar:
			if not file.isdir():
				dest = "." + file.name.replace("./frappe-bench/sites", "")
				asset_directory = os.path.dirname(dest)
				show = dest.replace("./assets/", "")

				if asset_directory not in directories_created:
					if not os.path.exists(asset_directory):
						os.makedirs(asset_directory, exist_ok=True)
					directories_created.add(asset_directory)

				tar.makefile(file, dest)
				click.echo(click.style("✔", fg="green") + f" Restored {show}")

	return directories_created


def download_frappe_assets(verbose=True) -> bool:
	"""Download and set up Frappe assets if they exist based on the current commit HEAD.
	Return True if correctly setup else return False.
	"""
	frappe_head = getoutput("cd ../apps/frappe && git rev-parse HEAD")

	if not frappe_head:
		return False

	try:
		url = get_assets_link(frappe_head)
		assets_archive = fetch_assets(url, frappe_head)
		setup_assets(assets_archive)
		build_missing_files()
		return True

	except AssetsDontExistError as e:
		click.secho(str(e), fg="yellow")

	except Exception as e:
		# TODO: log traceback in bench.log
		click.secho(str(e), fg="red")

	finally:
		try:
			shutil.rmtree(os.path.dirname(assets_archive))
		except Exception:
			pass

	return False


def symlink(target, link_name, overwrite=False):
	"""
	Create a symbolic link named link_name pointing to target.
	If link_name exists then FileExistsError is raised, unless overwrite=True.
	When trying to overwrite a directory, IsADirectoryError is raised.

	Source: https://stackoverflow.com/a/55742015/10309266
	"""

	if not overwrite:
		return os.symlink(target, link_name)

	# Create link to target with temporary filename
	while True:
		temp_link_name = f"tmp{frappe.generate_hash()}"

		# os.* functions mimic as closely as possible system functions
		# The POSIX symlink() returns EEXIST if link_name already exists
		# https://pubs.opengroup.org/onlinepubs/9699919799/functions/symlink.html
		try:
			os.symlink(target, temp_link_name)
			break
		except FileExistsError:
			pass

	# Replace link_name with temp_link_name
	try:
		# Pre-empt os.replace on a directory with a nicer message
		if os.path.isdir(link_name):
			raise IsADirectoryError(f"Cannot symlink over existing directory: '{link_name}'")
		try:
			shutil.move(temp_link_name, link_name)
		except AttributeError:
			os.renames(temp_link_name, link_name)
	except Exception:
		if os.path.islink(temp_link_name):
			os.remove(temp_link_name)
		raise


def setup():
	global app_paths, assets_path

	pymodules = []
	for app in frappe.get_all_apps(True):
		try:
			pymodules.append(frappe.get_module(app))
		except ImportError:
			pass
	app_paths = [os.path.dirname(pymodule.__file__) for pymodule in pymodules]
	assets_path = os.path.join(frappe.local.sites_path, "assets")


def bundle(
	mode,
	apps=None,
	hard_link=False,
	verbose=False,
	skip_frappe=False,
	files=None,
	save_metafiles=False,
	using_cached=False,
):
	"""concat / minify js files"""
	setup()
	make_asset_dirs(hard_link=hard_link)

	mode = "production" if mode == "production" else "build"
	command = f"yarn run {mode}"

	if apps:
		command += f" --apps {apps}"

	if skip_frappe:
		command += " --skip_frappe"

	if files:
		command += " --files {files}".format(files=",".join(files))

	if using_cached:
		command += " --using-cached"
	else:
		command += " --run-build-command"

	if save_metafiles:
		command += " --save-metafiles"

	check_node_executable()
	frappe_app_path = frappe.get_app_source_path("frappe")
	frappe.commands.popen(command, cwd=frappe_app_path, env=get_node_env(), raise_err=True)

	with suppress(Exception):
		frappe.cache.flushall()


def watch(apps=None):
	"""watch and rebuild if necessary"""
	setup()

	command = "yarn run watch"
	if apps:
		command += f" --apps {apps}"

	live_reload = frappe.utils.cint(os.environ.get("LIVE_RELOAD", frappe.conf.live_reload))

	if live_reload:
		command += " --live-reload"

	check_node_executable()
	frappe_app_path = frappe.get_app_source_path("frappe")
	frappe.commands.popen(command, cwd=frappe_app_path, env=get_node_env())


def check_node_executable():
	node_version = Version(subprocess.getoutput("node -v")[1:])
	warn = "⚠️ "
	if node_version.major < 18:
		click.echo(f"{warn} Please update your node version to 18")
	if not shutil.which("yarn"):
		click.echo(f"{warn} Please install yarn using below command and try again.\nnpm install -g yarn")
	click.echo()


def get_node_env():
	return {"NODE_OPTIONS": f"--max_old_space_size={get_safe_max_old_space_size()}"}


def get_safe_max_old_space_size():
	import psutil

	safe_max_old_space_size = 0
	try:
		total_memory = psutil.virtual_memory().total / (1024 * 1024)
		# reference for the safe limit assumption
		# https://nodejs.org/api/cli.html#cli_max_old_space_size_size_in_megabytes
		# set minimum value 1GB
		safe_max_old_space_size = max(1024, int(total_memory * 0.75))
	except Exception:
		pass

	return safe_max_old_space_size


def generate_assets_map():
	symlinks = {}

	for app_name in frappe.get_all_apps():
		app_doc_path = None

		pymodule = frappe.get_module(app_name)
		app_base_path = os.path.abspath(os.path.dirname(pymodule.__file__))
		app_public_path = os.path.join(app_base_path, "public")
		app_node_modules_path = os.path.join(app_base_path, "..", "node_modules")
		app_docs_path = os.path.join(app_base_path, "docs")
		app_www_docs_path = os.path.join(app_base_path, "www", "docs")

		app_assets = os.path.abspath(app_public_path)
		app_node_modules = os.path.abspath(app_node_modules_path)

		# {app}/public > assets/{app}
		if os.path.isdir(app_assets):
			symlinks[app_assets] = os.path.join(assets_path, app_name)

		# {app}/node_modules > assets/{app}/node_modules
		if os.path.isdir(app_node_modules):
			symlinks[app_node_modules] = os.path.join(assets_path, app_name, "node_modules")

		# {app}/docs > assets/{app}_docs
		if os.path.isdir(app_docs_path):
			app_doc_path = os.path.join(app_base_path, "docs")
		elif os.path.isdir(app_www_docs_path):
			app_doc_path = os.path.join(app_base_path, "www", "docs")
		if app_doc_path:
			app_docs = os.path.abspath(app_doc_path)
			symlinks[app_docs] = os.path.join(assets_path, app_name + "_docs")

	return symlinks


def setup_assets_dirs():
	for dir_path in (os.path.join(assets_path, x) for x in ("js", "css")):
		os.makedirs(dir_path, exist_ok=True)


def clear_broken_symlinks():
	for path in os.listdir(assets_path):
		path = os.path.join(assets_path, path)
		if os.path.islink(path) and not os.path.exists(path):
			os.remove(path)


def unstrip(message: str) -> str:
	"""Pads input string on the right side until the last available column in the terminal"""
	_len = len(message)
	try:
		max_str = os.get_terminal_size().columns
	except Exception:
		max_str = 80

	if _len < max_str:
		_rem = max_str - _len
	else:
		_rem = max_str % _len

	return f"{message}{' ' * _rem}"


def make_asset_dirs(hard_link=False):
	setup_assets_dirs()
	clear_broken_symlinks()
	symlinks = generate_assets_map()

	for source, target in symlinks.items():
		start_message = unstrip(f"{'Copying assets from' if hard_link else 'Linking'} {source} to {target}")
		fail_message = unstrip(f"Cannot {'copy' if hard_link else 'link'} {source} to {target}")

		# Used '\r' instead of '\x1b[1K\r' to print entire lines in smaller terminal sizes
		try:
			print(start_message, end="\r")
			link_assets_dir(source, target, hard_link=hard_link)
		except Exception as e:
			print(e)
			print(fail_message)

	click.echo(unstrip(click.style("✔", fg="green") + " Application Assets Linked") + "\n")


def link_assets_dir(source, target, hard_link=False):
	if not os.path.exists(source):
		return

	if os.path.exists(target):
		if os.path.islink(target):
			os.unlink(target)
		else:
			shutil.rmtree(target)

	if hard_link:
		shutil.copytree(source, target, dirs_exist_ok=True)
	else:
		symlink(source, target, overwrite=True)


def scrub_html_template(content):
	"""Return HTML content with removed whitespace and comments."""
	# remove whitespace to a single space
	content = WHITESPACE_PATTERN.sub(" ", content)

	# strip comments
	content = HTML_COMMENT_PATTERN.sub("", content)

	return content.replace("'", "'")


def html_to_js_template(path, content):
	"""Return HTML template content as Javascript code, by adding it to `frappe.templates`."""
	return """frappe.templates["{key}"] = '{content}';\n""".format(
		key=path.rsplit("/", 1)[-1][:-5], content=scrub_html_template(content)
	)
