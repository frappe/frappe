# imports - standard imports
import os
import shutil
import sys

# imports - third party imports
import click

# imports - module imports
import frappe
from frappe.commands import get_site, pass_context
from frappe.exceptions import SiteNotSpecifiedError


@click.command("new-site")
@click.argument("site")
@click.option("--db-name", help="Database name")
@click.option("--db-password", help="Database password")
@click.option(
	"--db-type",
	default="mariadb",
	type=click.Choice(["mariadb", "postgres"]),
	help='Optional "postgres" or "mariadb". Default is "mariadb"',
)
@click.option("--db-host", help="Database Host")
@click.option("--db-port", type=int, help="Database Port")
@click.option(
	"--db-root-username",
	"--mariadb-root-username",
	help='Root username for MariaDB or PostgreSQL, Default is "root"',
)
@click.option(
	"--db-root-password", "--mariadb-root-password", help="Root password for MariaDB or PostgreSQL"
)
@click.option(
	"--no-mariadb-socket",
	is_flag=True,
	default=False,
	help="Set MariaDB host to % and use TCP/IP Socket instead of using the UNIX Socket",
)
@click.option("--admin-password", help="Administrator password for new site", default=None)
@click.option("--verbose", is_flag=True, default=False, help="Verbose")
@click.option(
	"--force", help="Force restore if site/database already exists", is_flag=True, default=False
)
@click.option("--source-sql", "--source_sql", help="Initiate database with a SQL file")
@click.option("--install-app", multiple=True, help="Install app after installation")
@click.option(
	"--set-default", is_flag=True, default=False, help="Set the new site as default site"
)
def new_site(
	site,
	db_root_username=None,
	db_root_password=None,
	admin_password=None,
	verbose=False,
	source_sql=None,
	force=None,
	no_mariadb_socket=False,
	install_app=None,
	db_name=None,
	db_password=None,
	db_type=None,
	db_host=None,
	db_port=None,
	set_default=False,
):
	"Create a new site"
	from frappe.installer import _new_site, extract_sql_from_archive

	frappe.init(site=site, new_site=True)

	if source_sql:
		source_sql = extract_sql_from_archive(source_sql)

	_new_site(
		db_name,
		site,
		db_root_username=db_root_username,
		db_root_password=db_root_password,
		admin_password=admin_password,
		verbose=verbose,
		install_apps=install_app,
		source_sql=source_sql,
		force=force,
		no_mariadb_socket=no_mariadb_socket,
		db_password=db_password,
		db_type=db_type,
		db_host=db_host,
		db_port=db_port,
	)

	if set_default:
		use(site)


@click.command("restore")
@click.argument("sql-file-path")
@click.option(
	"--db-root-username",
	"--mariadb-root-username",
	help='Root username for MariaDB or PostgreSQL, Default is "root"',
)
@click.option(
	"--db-root-password", "--mariadb-root-password", help="Root password for MariaDB or PostgreSQL"
)
@click.option("--db-name", help="Database name for site in case it is a new one")
@click.option("--admin-password", help="Administrator password for new site")
@click.option("--install-app", multiple=True, help="Install app after installation")
@click.option(
	"--with-public-files", help="Restores the public files of the site, given path to its tar file"
)
@click.option(
	"--with-private-files", help="Restores the private files of the site, given path to its tar file"
)
@click.option(
	"--force",
	is_flag=True,
	default=False,
	help="Ignore the validations and downgrade warnings. This action is not recommended",
)
@click.option("--encryption-key", help="Backup encryption key")
@pass_context
def restore(
	context,
	sql_file_path,
	encryption_key=None,
	db_root_username=None,
	db_root_password=None,
	db_name=None,
	verbose=None,
	install_app=None,
	admin_password=None,
	force=None,
	with_public_files=None,
	with_private_files=None,
):
	"Restore site database from an sql file"
	from frappe.installer import (
		_new_site,
		extract_files,
		extract_sql_from_archive,
		is_downgrade,
		is_partial,
		validate_database_sql,
	)
	from frappe.utils.backups import Backup, get_or_generate_backup_encryption_key

	_backup = Backup(sql_file_path)

	site = get_site(context)
	frappe.init(site=site)
	force = context.force or force

	try:
		decompressed_file_name = extract_sql_from_archive(sql_file_path)
		if is_partial(decompressed_file_name):
			click.secho(
				"Partial Backup file detected. You cannot use a partial file to restore a Frappe site.",
				fg="red",
			)
			click.secho(
				"Use `bench partial-restore` to restore a partial backup to an existing site.", fg="yellow"
			)
			_backup.decryption_rollback()
			sys.exit(1)

	except UnicodeDecodeError:
		_backup.decryption_rollback()
		if encryption_key:
			click.secho("Encrypted backup file detected. Decrypting using provided key.", fg="yellow")
			_backup.backup_decryption(encryption_key)

		else:
			click.secho("Encrypted backup file detected. Decrypting using site config.", fg="yellow")
			encryption_key = get_or_generate_backup_encryption_key()
			_backup.backup_decryption(encryption_key)

		# Rollback on unsuccessful decryrption
		if not os.path.exists(sql_file_path):
			click.secho("Decryption failed. Please provide a valid key and try again.", fg="red")

			_backup.decryption_rollback()
			sys.exit(1)

		decompressed_file_name = extract_sql_from_archive(sql_file_path)

		if is_partial(decompressed_file_name):
			click.secho(
				"Partial Backup file detected. You cannot use a partial file to restore a Frappe site.",
				fg="red",
			)
			click.secho(
				"Use `bench partial-restore` to restore a partial backup to an existing site.", fg="yellow"
			)
			_backup.decryption_rollback()
			sys.exit(1)

	validate_database_sql(decompressed_file_name, _raise=not force)

	# dont allow downgrading to older versions of frappe without force
	if not force and is_downgrade(decompressed_file_name, verbose=True):
		warn_message = (
			"This is not recommended and may lead to unexpected behaviour. "
			"Do you want to continue anyway?"
		)
		click.confirm(warn_message, abort=True)

	try:
		_new_site(
			frappe.conf.db_name,
			site,
			db_root_username=db_root_username,
			db_root_password=db_root_password,
			admin_password=admin_password,
			verbose=context.verbose,
			install_apps=install_app,
			source_sql=decompressed_file_name,
			force=True,
			db_type=frappe.conf.db_type,
		)

	except Exception as err:
		print(err.args[1])
		_backup.decryption_rollback()
		sys.exit(1)

	# Removing temporarily created file
	if decompressed_file_name != sql_file_path:
		os.remove(decompressed_file_name)
		_backup.decryption_rollback()

	# Extract public and/or private files to the restored site, if user has given the path
	if with_public_files:
		# Decrypt data if there is a Key
		if encryption_key:
			_backup = Backup(with_public_files)
			_backup.backup_decryption(encryption_key)
			if not os.path.exists(with_public_files):
				_backup.decryption_rollback()
		public = extract_files(site, with_public_files)

		# Removing temporarily created file
		os.remove(public)
		_backup.decryption_rollback()

	if with_private_files:
		# Decrypt data if there is a Key
		if encryption_key:
			_backup = Backup(with_private_files)
			_backup.backup_decryption(encryption_key)
			if not os.path.exists(with_private_files):
				_backup.decryption_rollback()
		private = extract_files(site, with_private_files)

		# Removing temporarily created file
		os.remove(private)
		_backup.decryption_rollback()

	success_message = "Site {} has been restored{}".format(
		site, " with files" if (with_public_files or with_private_files) else ""
	)
	click.secho(success_message, fg="green")


@click.command("partial-restore")
@click.argument("sql-file-path")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--encryption-key", help="Backup encryption key")
@pass_context
def partial_restore(context, sql_file_path, verbose, encryption_key=None):
	from frappe.installer import extract_sql_from_archive, partial_restore
	from frappe.utils.backups import Backup, get_or_generate_backup_encryption_key

	if not os.path.exists(sql_file_path):
		print("Invalid path", sql_file_path)
		sys.exit(1)

	site = get_site(context)
	frappe.init(site=site)

	_backup = Backup(sql_file_path)

	verbose = context.verbose or verbose

	frappe.connect(site=site)
	try:
		decompressed_file_name = extract_sql_from_archive(sql_file_path)

		with open(decompressed_file_name) as f:
			header = " ".join(f.readline() for _ in range(5))

			# Check for full backup file
			if "Partial Backup" not in header:
				click.secho(
					"Full backup file detected.Use `bench restore` to restore a Frappe Site.", fg="red"
				)
				_backup.decryption_rollback()
				sys.exit(1)

	except UnicodeDecodeError:
		_backup.decryption_rollback()
		if encryption_key:
			click.secho("Encrypted backup file detected. Decrypting using provided key.", fg="yellow")
			key = encryption_key

		else:
			click.secho("Encrypted backup file detected. Decrypting using site config.", fg="yellow")
			key = get_or_generate_backup_encryption_key()

		_backup.backup_decryption(key)

		# Rollback on unsuccessful decryrption
		if not os.path.exists(sql_file_path):
			click.secho("Decryption failed. Please provide a valid key and try again.", fg="red")
			_backup.decryption_rollback()
			sys.exit(1)

		decompressed_file_name = extract_sql_from_archive(sql_file_path)

		with open(decompressed_file_name) as f:
			header = " ".join(f.readline() for _ in range(5))

			# Check for Full backup file.
			if "Partial Backup" not in header:
				click.secho(
					"Full Backup file detected.Use `bench restore` to restore a Frappe Site.", fg="red"
				)
				_backup.decryption_rollback()
				sys.exit(1)

	partial_restore(sql_file_path, verbose)

	# Removing temporarily created file
	_backup.decryption_rollback()
	if os.path.exists(sql_file_path.rstrip(".gz")):
		os.remove(sql_file_path.rstrip(".gz"))

	frappe.destroy()


@click.command("reinstall")
@click.option("--admin-password", help="Administrator Password for reinstalled site")
@click.option(
	"--db-root-username",
	"--mariadb-root-username",
	help='Root username for MariaDB or PostgreSQL, Default is "root"',
)
@click.option(
	"--db-root-password", "--mariadb-root-password", help="Root password for MariaDB or PostgreSQL"
)
@click.option("--yes", is_flag=True, default=False, help="Pass --yes to skip confirmation")
@pass_context
def reinstall(
	context, admin_password=None, db_root_username=None, db_root_password=None, yes=False
):
	"Reinstall site ie. wipe all data and start over"
	site = get_site(context)
	_reinstall(site, admin_password, db_root_username, db_root_password, yes, verbose=context.verbose)


def _reinstall(
	site, admin_password=None, db_root_username=None, db_root_password=None, yes=False, verbose=False
):
	from frappe.installer import _new_site

	if not yes:
		click.confirm("This will wipe your database. Are you sure you want to reinstall?", abort=True)
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.clear_cache()
		installed = frappe.get_installed_apps()
		frappe.clear_cache()
	except Exception:
		installed = []
	finally:
		if frappe.db:
			frappe.db.close()
		frappe.destroy()

	frappe.init(site=site)
	_new_site(
		frappe.conf.db_name,
		site,
		verbose=verbose,
		force=True,
		reinstall=True,
		install_apps=installed,
		db_root_username=db_root_username,
		db_root_password=db_root_password,
		admin_password=admin_password,
	)


@click.command("install-app")
@click.argument("apps", nargs=-1)
@click.option("--force", is_flag=True, default=False)
@pass_context
def install_app(context, apps, force=False):
	"Install a new app to site, supports multiple apps"
	from frappe.installer import install_app as _install_app

	exit_code = 0

	if not context.sites:
		raise SiteNotSpecifiedError

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()

		for app in apps:
			try:
				_install_app(app, verbose=context.verbose, force=force)
			except frappe.IncompatibleApp as err:
				err_msg = f":\n{err}" if str(err) else ""
				print(f"App {app} is Incompatible with Site {site}{err_msg}")
				exit_code = 1
			except Exception as err:
				err_msg = f": {str(err)}\n{frappe.get_traceback()}"
				print(f"An error occurred while installing {app}{err_msg}")
				exit_code = 1

		if not exit_code:
			frappe.db.commit()

		frappe.destroy()

	sys.exit(exit_code)


@click.command("list-apps")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
@pass_context
def list_apps(context, format):
	"List apps in site"

	summary_dict = {}

	def fix_whitespaces(text):
		if site == context.sites[-1]:
			text = text.rstrip()
		if len(context.sites) == 1:
			text = text.lstrip()
		return text

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		site_title = click.style(f"{site}", fg="green") if len(context.sites) > 1 else ""
		apps = frappe.get_single("Installed Applications").installed_applications

		if apps:
			name_len, ver_len = (max(len(x.get(y)) for x in apps) for y in ["app_name", "app_version"])
			template = f"{{0:{name_len}}} {{1:{ver_len}}} {{2}}"

			installed_applications = [
				template.format(app.app_name, app.app_version, app.git_branch) for app in apps
			]
			applications_summary = "\n".join(installed_applications)
			summary = f"{site_title}\n{applications_summary}\n"
			summary_dict[site] = [app.app_name for app in apps]

		else:
			installed_applications = frappe.get_installed_apps()
			applications_summary = "\n".join(installed_applications)
			summary = f"{site_title}\n{applications_summary}\n"
			summary_dict[site] = installed_applications

		summary = fix_whitespaces(summary)

		if format == "text" and applications_summary and summary:
			print(summary)

		frappe.destroy()

	if format == "json":
		click.echo(frappe.as_json(summary_dict))


@click.command("add-database-index")
@click.option("--doctype", help="DocType on which index needs to be added")
@click.option(
	"--column",
	multiple=True,
	help="Column to index. Multiple columns will create multi-column index in given order. To create a multiple, single column index, execute the command multiple times.",
)
@pass_context
def add_db_index(context, doctype, column):
	"Adds a new DB index and creates a property setter to persist it."
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	columns = column  # correct naming
	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.db.add_index(doctype, columns)
			if len(columns) == 1:
				make_property_setter(
					doctype,
					columns[0],
					property="search_index",
					value="1",
					property_type="Check",
					for_doctype=False,  # Applied on docfield
				)
			frappe.db.commit()
		finally:
			frappe.destroy()

	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("describe-database-table")
@click.option("--doctype", help="DocType to describe")
@click.option(
	"--column",
	multiple=True,
	help="Explicitly fetch accurate cardinality from table data. This can be quite slow on large tables.",
)
@pass_context
def describe_database_table(context, doctype, column):
	"""Describes various statistics about the table.

	This is useful to build integration like
	This includes:
	1. Schema
	2. Indexes
	3. stats - total count of records
	4. if column is specified then extra stats are generated for column:
	        Distinct values count in column
	"""
	import json

	for site in context.sites:
		frappe.connect(site=site)
		try:
			data = _extract_table_stats(doctype, column)
			# NOTE: Do not print anything else in this to avoid clobbering the output.
			print(json.dumps(data, indent=2))
		finally:
			frappe.destroy()

	if not context.sites:
		raise SiteNotSpecifiedError


def _extract_table_stats(doctype: str, columns: list[str]) -> dict:
	from frappe.utils import cint, cstr, get_table_name

	def sql_bool(val):
		return cstr(val).lower() in ("yes", "1", "true")

	table = get_table_name(doctype, wrap_in_backticks=True)

	schema = []
	for field in frappe.db.sql(f"describe {table}", as_dict=True):
		schema.append(
			{
				"column": field["Field"],
				"type": field["Type"],
				"is_nullable": sql_bool(field["Null"]),
				"default": field["Default"],
			}
		)

	def update_cardinality(column, value):
		for col in schema:
			if col["column"] == column:
				col["cardinality"] = value
				break

	indexes = []
	for idx in frappe.db.sql(f"show index from {table}", as_dict=True):
		indexes.append(
			{
				"unique": not sql_bool(idx["Non_unique"]),
				"cardinality": idx["Cardinality"],
				"name": idx["Key_name"],
				"sequence": idx["Seq_in_index"],
				"nullable": sql_bool(idx["Null"]),
				"column": idx["Column_name"],
				"type": idx["Index_type"],
			}
		)
		if idx["Seq_in_index"] == 1:
			update_cardinality(idx["Column_name"], idx["Cardinality"])

	total_rows = cint(
		frappe.db.sql(
			f"""select table_rows
			   from  information_schema.tables
			   where table_name = 'tab{doctype}'"""
		)[0][0]
	)

	# fetch accurate cardinality for columns by query. WARN: This can take a lot of time.
	for column in columns:
		cardinality = frappe.db.sql(f"select count(distinct {column}) from {table}")[0][0]
		update_cardinality(column, cardinality)

	return {
		"table_name": table.strip("`"),
		"total_rows": total_rows,
		"schema": schema,
		"indexes": indexes,
	}


@click.command("add-system-manager")
@click.argument("email")
@click.option("--first-name")
@click.option("--last-name")
@click.option("--password")
@click.option("--send-welcome-email", default=False, is_flag=True)
@pass_context
def add_system_manager(context, email, first_name, last_name, send_welcome_email, password):
	"Add a new system manager to a site"
	import frappe.utils.user

	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.utils.user.add_system_manager(email, first_name, last_name, send_welcome_email, password)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("add-user")
@click.argument("email")
@click.option("--first-name")
@click.option("--last-name")
@click.option("--password")
@click.option("--user-type")
@click.option("--add-role", multiple=True)
@click.option("--send-welcome-email", default=False, is_flag=True)
@pass_context
def add_user_for_sites(
	context, email, first_name, last_name, user_type, send_welcome_email, password, add_role
):
	"Add user to a site"
	import frappe.utils.user

	for site in context.sites:
		frappe.connect(site=site)
		try:
			add_new_user(email, first_name, last_name, user_type, send_welcome_email, password, add_role)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("disable-user")
@click.argument("email")
@pass_context
def disable_user(context, email):
	site = get_site(context)
	with frappe.init_site(site):
		frappe.connect()
		user = frappe.get_doc("User", email)
		user.enabled = 0
		user.save(ignore_permissions=True)
		frappe.db.commit()


@click.command("migrate")
@click.option("--skip-failing", is_flag=True, help="Skip patches that fail to run")
@click.option("--skip-search-index", is_flag=True, help="Skip search indexing for web documents")
@pass_context
def migrate(context, skip_failing=False, skip_search_index=False):
	"Run patches, sync schema and rebuild files/translations"
	from traceback_with_variables import activate_by_import

	from frappe.migrate import SiteMigration

	for site in context.sites:
		click.secho(f"Migrating {site}", fg="green")
		try:
			SiteMigration(
				skip_failing=skip_failing,
				skip_search_index=skip_search_index,
			).run(site=site)
		finally:
			print()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("migrate-to")
@click.argument("frappe_provider")
@pass_context
def migrate_to(context, frappe_provider):
	"Migrates site to the specified provider"
	from frappe.integrations.frappe_providers import migrate_to

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		migrate_to(site, frappe_provider)
		frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("run-patch")
@click.argument("module")
@click.option("--force", is_flag=True)
@pass_context
def run_patch(context, module, force):
	"Run a particular patch"
	import frappe.modules.patch_handler

	for site in context.sites:
		frappe.init(site=site)
		try:
			frappe.connect()
			frappe.modules.patch_handler.run_single(module, force=force or context.force)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("reload-doc")
@click.argument("module")
@click.argument("doctype")
@click.argument("docname")
@pass_context
def reload_doc(context, module, doctype, docname):
	"Reload schema for a DocType"
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.reload_doc(module, doctype, docname, force=context.force)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("reload-doctype")
@click.argument("doctype")
@pass_context
def reload_doctype(context, doctype):
	"Reload schema for a DocType"
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			frappe.reload_doctype(doctype, force=context.force)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("add-to-hosts")
@pass_context
def add_to_hosts(context):
	"Add site to hosts"
	for site in context.sites:
		frappe.commands.popen(f"echo 127.0.0.1\t{site} | sudo tee -a /etc/hosts")
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("use")
@click.argument("site")
def _use(site, sites_path="."):
	"Set a default site"
	use(site, sites_path=sites_path)


def use(site, sites_path="."):
	if os.path.exists(os.path.join(sites_path, site)):
		with open(os.path.join(sites_path, "currentsite.txt"), "w") as sitefile:
			sitefile.write(site)
		print(f"Current Site set to {site}")
	else:
		print(f"Site {site} does not exist")


@click.command("backup")
@click.option("--with-files", default=False, is_flag=True, help="Take backup with files")
@click.option(
	"--include",
	"--only",
	"-i",
	default="",
	type=str,
	help="Specify the DocTypes to backup seperated by commas",
)
@click.option(
	"--exclude",
	"-e",
	default="",
	type=str,
	help="Specify the DocTypes to not backup seperated by commas",
)
@click.option(
	"--backup-path", default=None, help="Set path for saving all the files in this operation"
)
@click.option("--backup-path-db", default=None, help="Set path for saving database file")
@click.option("--backup-path-files", default=None, help="Set path for saving public file")
@click.option("--backup-path-private-files", default=None, help="Set path for saving private file")
@click.option("--backup-path-conf", default=None, help="Set path for saving config file")
@click.option(
	"--ignore-backup-conf", default=False, is_flag=True, help="Ignore excludes/includes set in config"
)
@click.option("--verbose", default=False, is_flag=True, help="Add verbosity")
@click.option("--compress", default=False, is_flag=True, help="Compress private and public files")
@pass_context
def backup(
	context,
	with_files=False,
	backup_path=None,
	backup_path_db=None,
	backup_path_files=None,
	backup_path_private_files=None,
	backup_path_conf=None,
	ignore_backup_conf=False,
	verbose=False,
	compress=False,
	include="",
	exclude="",
):
	"Backup"

	from frappe.utils.backups import scheduled_backup

	verbose = verbose or context.verbose
	exit_code = 0

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			odb = scheduled_backup(
				ignore_files=not with_files,
				backup_path=backup_path,
				backup_path_db=backup_path_db,
				backup_path_files=backup_path_files,
				backup_path_private_files=backup_path_private_files,
				backup_path_conf=backup_path_conf,
				ignore_conf=ignore_backup_conf,
				include_doctypes=include,
				exclude_doctypes=exclude,
				compress=compress,
				verbose=verbose,
				force=True,
			)
		except Exception:
			click.secho(
				f"Backup failed for Site {site}. Database or site_config.json may be corrupted",
				fg="red",
			)
			if verbose:
				print(frappe.get_traceback())
			exit_code = 1
			continue
		if frappe.get_system_settings("encrypt_backup") and frappe.get_site_config().encryption_key:
			click.secho(
				"Backup encryption is turned on. Please note the backup encryption key.", fg="yellow"
			)

		odb.print_summary()
		click.secho(
			"Backup for Site {} has been successfully completed{}".format(
				site, " with files" if with_files else ""
			),
			fg="green",
		)
		frappe.destroy()

	if not context.sites:
		raise SiteNotSpecifiedError

	sys.exit(exit_code)


@click.command("remove-from-installed-apps")
@click.argument("app")
@pass_context
def remove_from_installed_apps(context, app):
	"Remove app from site's installed-apps list"
	from frappe.installer import remove_from_installed_apps

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_from_installed_apps(app)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("uninstall-app")
@click.argument("app")
@click.option(
	"--yes",
	"-y",
	help="To bypass confirmation prompt for uninstalling the app",
	is_flag=True,
	default=False,
)
@click.option(
	"--dry-run", help="List all doctypes that will be deleted", is_flag=True, default=False
)
@click.option("--no-backup", help="Do not backup the site", is_flag=True, default=False)
@click.option("--force", help="Force remove app from site", is_flag=True, default=False)
@pass_context
def uninstall(context, app, dry_run, yes, no_backup, force):
	"Remove app and linked modules from site"
	from frappe.installer import remove_app

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_app(app_name=app, dry_run=dry_run, yes=yes, no_backup=no_backup, force=force)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("drop-site")
@click.argument("site")
@click.option(
	"--db-root-username",
	"--mariadb-root-username",
	"--root-login",
	help='Root username for MariaDB or PostgreSQL, Default is "root"',
)
@click.option(
	"--db-root-password",
	"--mariadb-root-password",
	"--root-password",
	help="Root password for MariaDB or PostgreSQL",
)
@click.option("--archived-sites-path")
@click.option("--no-backup", is_flag=True, default=False)
@click.option(
	"--force", help="Force drop-site even if an error is encountered", is_flag=True, default=False
)
def drop_site(
	site,
	db_root_username="root",
	db_root_password=None,
	archived_sites_path=None,
	force=False,
	no_backup=False,
):
	_drop_site(site, db_root_username, db_root_password, archived_sites_path, force, no_backup)


def _drop_site(
	site,
	db_root_username=None,
	db_root_password=None,
	archived_sites_path=None,
	force=False,
	no_backup=False,
):
	"Remove site from database and filesystem"
	from frappe.database import drop_user_and_database
	from frappe.utils.backups import scheduled_backup

	frappe.init(site=site)
	frappe.connect()

	try:
		if not no_backup:
			click.secho(f"Taking backup of {site}", fg="green")
			odb = scheduled_backup(ignore_files=False, ignore_conf=True, force=True, verbose=True)
			odb.print_summary()
	except Exception as err:
		if force:
			pass
		else:
			messages = [
				"=" * 80,
				f"Error: The operation has stopped because backup of {site}'s database failed.",
				f"Reason: {str(err)}\n",
				"Fix the issue and try again.",
				"Hint: Use 'bench drop-site {0} --force' to force the removal of {0}".format(site),
			]
			click.echo("\n".join(messages))
			sys.exit(1)

	click.secho("Dropping site database and user", fg="green")
	drop_user_and_database(frappe.conf.db_name, db_root_username, db_root_password)

	archived_sites_path = archived_sites_path or os.path.join(
		frappe.get_app_path("frappe"), "..", "..", "..", "archived", "sites"
	)
	archived_sites_path = os.path.realpath(archived_sites_path)

	click.secho(f"Moving site to archive under {archived_sites_path}", fg="green")
	os.makedirs(archived_sites_path, exist_ok=True)
	move(archived_sites_path, site)


def move(dest_dir, site):
	if not os.path.isdir(dest_dir):
		raise Exception("destination is not a directory or does not exist")

	frappe.init(site)
	old_path = frappe.utils.get_site_path()
	new_path = os.path.join(dest_dir, site)

	# check if site dump of same name already exists
	site_dump_exists = True
	count = 0
	while site_dump_exists:
		final_new_path = new_path + (count and str(count) or "")
		site_dump_exists = os.path.exists(final_new_path)
		count = int(count or 0) + 1

	shutil.move(old_path, final_new_path)
	frappe.destroy()
	return final_new_path


@click.command("set-password")
@click.argument("user")
@click.argument("password", required=False)
@click.option(
	"--logout-all-sessions", help="Log out from all sessions", is_flag=True, default=False
)
@pass_context
def set_password(context, user, password=None, logout_all_sessions=False):
	"Set password for a user on a site"
	if not context.sites:
		raise SiteNotSpecifiedError

	for site in context.sites:
		set_user_password(site, user, password, logout_all_sessions)


@click.command("set-admin-password")
@click.argument("admin-password", required=False)
@click.option(
	"--logout-all-sessions", help="Log out from all sessions", is_flag=True, default=False
)
@pass_context
def set_admin_password(context, admin_password=None, logout_all_sessions=False):
	"Set Administrator password for a site"
	if not context.sites:
		raise SiteNotSpecifiedError

	for site in context.sites:
		set_user_password(site, "Administrator", admin_password, logout_all_sessions)


def set_user_password(site, user, password, logout_all_sessions=False):
	import getpass

	from frappe.utils.password import update_password

	try:
		frappe.init(site=site)

		while not password:
			password = getpass.getpass(f"{user}'s password for {site}: ")

		frappe.connect()
		if not frappe.db.exists("User", user):
			print(f"User {user} does not exist")
			sys.exit(1)

		update_password(user=user, pwd=password, logout_all_sessions=logout_all_sessions)
		frappe.db.commit()
	finally:
		frappe.destroy()


@click.command("set-last-active-for-user")
@click.option("--user", help="Setup last active date for user")
@pass_context
def set_last_active_for_user(context, user=None):
	"Set users last active date to current datetime"
	from frappe.core.doctype.user.user import get_system_users
	from frappe.utils import now_datetime

	site = get_site(context)

	with frappe.init_site(site):
		frappe.connect()
		if not user:
			user = get_system_users(limit=1)
			if len(user) > 0:
				user = user[0]
			else:
				return

		frappe.db.set_value("User", user, "last_active", now_datetime())
		frappe.db.commit()


@click.command("publish-realtime")
@click.argument("event")
@click.option("--message")
@click.option("--room")
@click.option("--user")
@click.option("--doctype")
@click.option("--docname")
@click.option("--after-commit")
@pass_context
def publish_realtime(context, event, message, room, user, doctype, docname, after_commit):
	"Publish realtime event from bench"
	from frappe import publish_realtime

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			publish_realtime(
				event,
				message=message,
				room=room,
				user=user,
				doctype=doctype,
				docname=docname,
				after_commit=after_commit,
			)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("browse")
@click.argument("site", required=False)
@click.option("--user", required=False, help="Login as user")
@pass_context
def browse(context, site, user=None):
	"""Opens the site on web browser"""
	from frappe.auth import CookieManager, LoginManager

	site = get_site(context, raise_err=False) or site

	if not site:
		raise SiteNotSpecifiedError

	if site not in frappe.utils.get_sites():
		click.echo(f"\nSite named {click.style(site, bold=True)} doesn't exist\n", err=True)
		sys.exit(1)

	frappe.init(site=site)
	frappe.connect()

	sid = ""
	if user:
		if frappe.conf.developer_mode or user == "Administrator":
			frappe.utils.set_request(path="/")
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(user)
			sid = f"/app?sid={frappe.session.sid}"
		else:
			click.echo("Please enable developer mode to login as a user")

	url = f"{frappe.utils.get_site_url(site)}{sid}"

	if user == "Administrator":
		click.echo(f"Login URL: {url}")

	click.launch(url)


@click.command("start-recording")
@pass_context
def start_recording(context):
	import frappe.recorder

	for site in context.sites:
		frappe.init(site=site)
		frappe.set_user("Administrator")
		frappe.recorder.start()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("stop-recording")
@pass_context
def stop_recording(context):
	import frappe.recorder

	for site in context.sites:
		frappe.init(site=site)
		frappe.set_user("Administrator")
		frappe.recorder.stop()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("ngrok")
@click.option(
	"--bind-tls", is_flag=True, default=False, help="Returns a reference to the https tunnel."
)
@pass_context
def start_ngrok(context, bind_tls):
	from pyngrok import ngrok

	site = get_site(context)
	frappe.init(site=site)

	port = frappe.conf.http_port or frappe.conf.webserver_port
	tunnel = ngrok.connect(addr=str(port), host_header=site, bind_tls=bind_tls)
	print(f"Public URL: {tunnel.public_url}")
	print("Inspect logs at http://localhost:4040")

	ngrok_process = ngrok.get_ngrok_process()
	try:
		# Block until CTRL-C or some other terminating event
		ngrok_process.proc.wait()
	except KeyboardInterrupt:
		print("Shutting down server...")
		frappe.destroy()
		ngrok.kill()


@click.command("build-search-index")
@pass_context
def build_search_index(context):
	from frappe.search.website_search import build_index_for_all_routes

	site = get_site(context)
	if not site:
		raise SiteNotSpecifiedError

	print(f"Building search index for {site}")
	frappe.init(site=site)
	frappe.connect()
	try:
		build_index_for_all_routes()
	finally:
		frappe.destroy()


@click.command("clear-log-table")
@click.option("--doctype", required=True, type=str, help="Log DocType")
@click.option("--days", type=int, help="Keep records for days")
@click.option("--no-backup", is_flag=True, default=False, help="Do not backup the table")
@pass_context
def clear_log_table(context, doctype, days, no_backup):

	"""If any logtype table grows too large then clearing it with DELETE query
	is not feasible in reasonable time. This command copies recent data to new
	table and replaces current table with new smaller table.


	ref: https://mariadb.com/kb/en/big-deletes/#deleting-more-than-half-a-table
	"""
	from frappe.core.doctype.log_settings.log_settings import LOG_DOCTYPES
	from frappe.core.doctype.log_settings.log_settings import clear_log_table as clear_logs
	from frappe.utils.backups import scheduled_backup

	if not context.sites:
		raise SiteNotSpecifiedError

	if doctype not in LOG_DOCTYPES:
		raise frappe.ValidationError(f"Unsupported logging DocType: {doctype}")

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()

		if not no_backup:
			scheduled_backup(
				ignore_conf=False,
				include_doctypes=doctype,
				ignore_files=True,
				force=True,
			)
			click.echo(f"Backed up {doctype}")

		try:
			click.echo(f"Copying {doctype} records from last {days} days to temporary table.")
			clear_logs(doctype, days=days)
		except Exception as e:
			click.echo(f"Log cleanup for {doctype} failed:\n{e}")
			sys.exit(1)
		else:
			click.secho(f"Cleared {doctype} records older than {days} days", fg="green")


@click.command("trim-database")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be deleted")
@click.option(
	"--format", "-f", default="text", type=click.Choice(["json", "text"]), help="Output format"
)
@click.option("--no-backup", is_flag=True, default=False, help="Do not backup the site")
@click.option(
	"--yes",
	"-y",
	help="To bypass confirmation prompt.",
	is_flag=True,
	default=False,
)
@pass_context
def trim_database(context, dry_run, format, no_backup, yes=False):
	"""Remove database tables for deleted DocTypes."""

	if not context.sites:
		raise SiteNotSpecifiedError

	from frappe.utils.backups import scheduled_backup

	ALL_DATA = {}

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()

		TABLES_TO_DROP = []
		STANDARD_TABLES = get_standard_tables()
		information_schema = frappe.qb.Schema("information_schema")
		table_name = frappe.qb.Field("table_name").as_("name")

		queried_result = (
			frappe.qb.from_(information_schema.tables)
			.select(table_name)
			.where(information_schema.tables.table_schema == frappe.conf.db_name)
			.where(information_schema.tables.table_type == "BASE TABLE")
			.run()
		)

		database_tables = [x[0] for x in queried_result]
		doctype_tables = frappe.get_all("DocType", pluck="name")

		for x in database_tables:
			if not x.startswith("tab"):
				continue
			doctype = x.replace("tab", "", 1)
			if not (doctype in doctype_tables or x.startswith("__") or x in STANDARD_TABLES):
				TABLES_TO_DROP.append(x)

		if not TABLES_TO_DROP:
			if format == "text":
				click.secho(f"No ghost tables found in {frappe.local.site}...Great!", fg="green")
		else:
			if not yes:
				print("Following tables will be dropped:")
				print("\n".join(f"* {dt}" for dt in TABLES_TO_DROP))
				click.confirm("Do you want to continue?", abort=True)

			if not (no_backup or dry_run):
				if format == "text":
					print(f"Backing Up Tables: {', '.join(TABLES_TO_DROP)}")

				odb = scheduled_backup(
					ignore_conf=False,
					include_doctypes=",".join(x.replace("tab", "", 1) for x in TABLES_TO_DROP),
					ignore_files=True,
					force=True,
				)
				if format == "text":
					odb.print_summary()
					print("\nTrimming Database")

			for table in TABLES_TO_DROP:
				if format == "text":
					print(f"* Dropping Table '{table}'...")
				if not dry_run:
					frappe.db.sql_ddl(f"drop table `{table}`")

			ALL_DATA[frappe.local.site] = TABLES_TO_DROP
		frappe.destroy()

	if format == "json":
		import json

		print(json.dumps(ALL_DATA, indent=1))


def get_standard_tables():
	import re

	tables = []
	sql_file = os.path.join(
		"..",
		"apps",
		"frappe",
		"frappe",
		"database",
		frappe.conf.db_type,
		f"framework_{frappe.conf.db_type}.sql",
	)
	content = open(sql_file).read().splitlines()

	for line in content:
		table_found = re.search(r"""CREATE TABLE ("|`)(.*)?("|`) \(""", line)
		if table_found:
			tables.append(table_found.group(2))

	return tables


@click.command("trim-tables")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be deleted")
@click.option(
	"--format", "-f", default="table", type=click.Choice(["json", "table"]), help="Output format"
)
@click.option("--no-backup", is_flag=True, default=False, help="Do not backup the site")
@pass_context
def trim_tables(context, dry_run, format, no_backup):
	if not context.sites:
		raise SiteNotSpecifiedError

	from frappe.model.meta import trim_tables
	from frappe.utils.backups import scheduled_backup

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()

		if not (no_backup or dry_run):
			click.secho(f"Taking backup for {frappe.local.site}", fg="green")
			odb = scheduled_backup(ignore_files=False, force=True)
			odb.print_summary()

		try:
			trimmed_data = trim_tables(dry_run=dry_run, quiet=format == "json")

			if format == "table" and not dry_run:
				click.secho(f"The following data have been removed from {frappe.local.site}", fg="green")

			handle_data(trimmed_data, format=format)
		finally:
			frappe.destroy()


def handle_data(data: dict, format="json"):
	if format == "json":
		import json

		print(json.dumps({frappe.local.site: data}, indent=1, sort_keys=True))
	else:
		from frappe.utils.commands import render_table

		data = [["DocType", "Fields"]] + [[table, ", ".join(columns)] for table, columns in data.items()]
		render_table(data)


def add_new_user(
	email,
	first_name=None,
	last_name=None,
	user_type="System User",
	send_welcome_email=False,
	password=None,
	role=None,
):
	user = frappe.new_doc("User")
	user.update(
		{
			"name": email,
			"email": email,
			"enabled": 1,
			"first_name": first_name or email,
			"last_name": last_name,
			"user_type": user_type,
			"send_welcome_email": 1 if send_welcome_email else 0,
		}
	)
	user.insert()
	user.add_roles(*role)
	if password:
		from frappe.utils.password import update_password

		update_password(user=user.name, pwd=password)


commands = [
	add_system_manager,
	add_user_for_sites,
	add_db_index,
	describe_database_table,
	backup,
	drop_site,
	install_app,
	list_apps,
	migrate,
	migrate_to,
	new_site,
	reinstall,
	reload_doc,
	reload_doctype,
	remove_from_installed_apps,
	restore,
	run_patch,
	set_password,
	set_admin_password,
	uninstall,
	disable_user,
	_use,
	set_last_active_for_user,
	publish_realtime,
	browse,
	start_recording,
	stop_recording,
	add_to_hosts,
	start_ngrok,
	build_search_index,
	partial_restore,
	trim_tables,
	trim_database,
	clear_log_table,
]
