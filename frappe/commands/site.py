from __future__ import unicode_literals, absolute_import
import click
import hashlib, os
import frappe
from frappe.commands import pass_context, get_site
from frappe.commands.scheduler import _is_scheduler_enabled
from frappe.limits import update_limits, get_limits
from frappe.installer import update_site_config

@click.command('new-site')
@click.argument('site')
@click.option('--db-name', help='Database name')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--admin-password', help='Administrator password for new site', default=None)
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
@click.option('--force', help='Force restore if site/database already exists', is_flag=True, default=False)
@click.option('--source_sql', help='Initiate database with a SQL file')
@click.option('--install-app', multiple=True, help='Install app after installation')
def new_site(site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None, verbose=False, install_apps=None, source_sql=None, force=None, install_app=None, db_name=None):
	"Create a new site"
	if not db_name:
		db_name = hashlib.sha1(site).hexdigest()[:10]

	frappe.init(site=site, new_site=True)
	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password, verbose=verbose, install_apps=install_app, source_sql=source_sql, force=force)
	if len(frappe.utils.get_sites()) == 1:
		use(site)

def _new_site(db_name, site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None, verbose=False, install_apps=None, source_sql=None,force=False, reinstall=False):
	"Install a new Frappe site"
	from frappe.installer import install_db, make_site_dirs
	from frappe.installer import install_app as _install_app
	import frappe.utils.scheduler

	frappe.init(site=site)

	try:
		# enable scheduler post install?
		enable_scheduler = _is_scheduler_enabled()
	except:
		enable_scheduler = False

	install_db(root_login=mariadb_root_username, root_password=mariadb_root_password, db_name=db_name, admin_password=admin_password, verbose=verbose, source_sql=source_sql,force=force, reinstall=reinstall)
	make_site_dirs()
	_install_app("frappe", verbose=verbose, set_as_patched=not source_sql)

	if frappe.conf.get("install_apps"):
		for app in frappe.conf.install_apps:
			_install_app(app, verbose=verbose, set_as_patched=not source_sql)

	if install_apps:
		for app in install_apps:
			_install_app(app, verbose=verbose, set_as_patched=not source_sql)

	frappe.utils.scheduler.toggle_scheduler(enable_scheduler)
	frappe.db.commit()

	scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
	print "*** Scheduler is", scheduler_status, "***"
	frappe.destroy()

@click.command('restore')
@click.argument('sql-file-path')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--db-name', help='Database name for site in case it is a new one')
@click.option('--admin-password', help='Administrator password for new site')
@click.option('--install-app', multiple=True, help='Install app after installation')
@click.option('--with-public-files', help='Restores the public files of the site, given path to its tar file')
@click.option('--with-private-files', help='Restores the private files of the site, given path to its tar file')
@pass_context
def restore(context, sql_file_path, mariadb_root_username=None, mariadb_root_password=None, db_name=None, verbose=None, install_app=None, admin_password=None, force=None, with_public_files=None, with_private_files=None):
	"Restore site database from an sql file"
	from frappe.installer import extract_sql_gzip, extract_tar_files
	# Extract the gzip file if user has passed *.sql.gz file instead of *.sql file
	if sql_file_path.endswith('sql.gz'):
		sql_file_path = extract_sql_gzip(os.path.abspath(sql_file_path))

	site = get_site(context)
	frappe.init(site=site)
	db_name = db_name or frappe.conf.db_name or hashlib.sha1(site).hexdigest()[:10]
	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password, verbose=context.verbose, install_apps=install_app, source_sql=sql_file_path, force=context.force)

	# Extract public and/or private files to the restored site, if user has given the path
	if with_public_files:
		extract_tar_files(site, with_public_files, 'public')

	if with_private_files:
		extract_tar_files(site, with_private_files, 'private')

@click.command('reinstall')
@pass_context
def reinstall(context):
	"Reinstall site ie. wipe all data and start over"
	site = get_site(context)
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
	_new_site(frappe.conf.db_name, site, verbose=context.verbose, force=True, reinstall=True, install_apps=installed)

@click.command('install-app')
@click.argument('app')
@pass_context
def install_app(context, app):
	"Install a new app to site"
	from frappe.installer import install_app as _install_app
	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		try:
			_install_app(app, verbose=context.verbose)
		finally:
			frappe.destroy()

@click.command('list-apps')
@pass_context
def list_apps(context):
	"List apps in site"
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	print "\n".join(frappe.get_installed_apps())
	frappe.destroy()

@click.command('add-system-manager')
@click.argument('email')
@click.option('--first-name')
@click.option('--last-name')
@pass_context
def add_system_manager(context, email, first_name, last_name):
	"Add a new system manager to a site"
	import frappe.utils.user
	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.utils.user.add_system_manager(email, first_name, last_name)
			frappe.db.commit()
		finally:
			frappe.destroy()

@click.command('migrate')
@click.option('--rebuild-website', help="Rebuild webpages after migration")
@pass_context
def migrate(context, rebuild_website=False):
	"Run patches, sync schema and rebuild files/translations"
	from frappe.migrate import migrate

	for site in context.sites:
		print 'Migrating', site
		frappe.init(site=site)
		frappe.connect()
		try:
			migrate(context.verbose, rebuild_website=rebuild_website)
		finally:
			frappe.destroy()

@click.command('run-patch')
@click.argument('module')
@pass_context
def run_patch(context, module):
	"Run a particular patch"
	import frappe.modules.patch_handler
	for site in context.sites:
		frappe.init(site=site)
		try:
			frappe.connect()
			frappe.modules.patch_handler.run_single(module, force=context.force)
		finally:
			frappe.destroy()

@click.command('reload-doc')
@click.argument('module')
@click.argument('doctype')
@click.argument('docname')
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


@click.command('use')
@click.argument('site')
def _use(site, sites_path='.'):
	"Set a default site"
	use(site, sites_path=sites_path)

def use(site, sites_path='.'):
	with open(os.path.join(sites_path,  "currentsite.txt"), "w") as sitefile:
		sitefile.write(site)

@click.command('backup')
@click.option('--with-files', default=False, is_flag=True, help="Take backup with files")
@pass_context
def backup(context, with_files=False, backup_path_db=None, backup_path_files=None,
	backup_path_private_files=None, quiet=False):
	"Backup"
	from frappe.utils.backups import scheduled_backup
	verbose = context.verbose
	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, backup_path_private_files=backup_path_private_files, force=True)
		if verbose:
			from frappe.utils import now
			print "database backup taken -", odb.backup_path_db, "- on", now()
			if with_files:
				print "files backup taken -", odb.backup_path_files, "- on", now()
				print "private files backup taken -", odb.backup_path_private_files, "- on", now()

		frappe.destroy()

@click.command('remove-from-installed-apps')
@click.argument('app')
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

@click.command('uninstall-app')
@click.argument('app')
@click.option('--dry-run', help='List all doctypes that will be deleted', is_flag=True, default=False)
@pass_context
def uninstall(context, app, dry_run=False):
	"Remove app and linked modules from site"
	from frappe.installer import remove_app
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_app(app, dry_run)
		finally:
			frappe.destroy()


@click.command('drop-site')
@click.argument('site')
@click.option('--root-login', default='root')
@click.option('--root-password')
@click.option('--archived-sites-path')
def drop_site(site, root_login='root', root_password=None, archived_sites_path=None):
	"Remove site from database and filesystem"
	from frappe.installer import get_current_host, make_connection
	from frappe.model.db_schema import DbManager
	from frappe.utils.backups import scheduled_backup

	frappe.init(site=site)
	frappe.connect()
	scheduled_backup(ignore_files=False, force=True)

	db_name = frappe.local.conf.db_name
	frappe.local.db = make_connection(root_login, root_password)
	dbman = DbManager(frappe.local.db)
	dbman.delete_user(db_name, get_current_host())
	dbman.drop_database(db_name)

	if not archived_sites_path:
		archived_sites_path = os.path.join(frappe.get_app_path('frappe'), '..', '..', '..', 'archived_sites')

	if not os.path.exists(archived_sites_path):
		os.mkdir(archived_sites_path)

	move(archived_sites_path, site)

def move(dest_dir, site):
	import os
	if not os.path.isdir(dest_dir):
		raise Exception, "destination is not a directory or does not exist"

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

	os.rename(old_path, final_new_path)
	frappe.destroy()
	return final_new_path


@click.command('set-admin-password')
@click.argument('admin-password')
@pass_context
def set_admin_password(context, admin_password):
	"Set Administrator password for a site"
	import getpass
	from frappe.utils.password import update_password

	for site in context.sites:
		try:
			frappe.init(site=site)

			while not admin_password:
				admin_password = getpass.getpass("Administrator's password for {0}: ".format(site))

			frappe.connect()
			update_password('Administrator', admin_password)
			frappe.db.commit()
			admin_password = None
		finally:
			frappe.destroy()


@click.command('set-limit')
@click.option('--site', help='site name')
@click.argument('limit', type=click.Choice(['emails', 'space', 'users', 'expiry',
	'support_email', 'support_chat', 'upgrade_link']))
@click.argument('value')
@pass_context
def set_limit(context, site, limit, value):
	"""Sets user / space / email limit for a site"""
	import datetime
	if not site:
		site = get_site(context)

	with frappe.init_site(site):
		if limit=='expiry':
			try:
				datetime.datetime.strptime(value, '%Y-%m-%d')
			except ValueError:
				raise ValueError("Incorrect data format, should be YYYY-MM-DD")

		elif limit=='space':
			value = float(value)

		elif limit in ('users', 'emails'):
			value = int(value)

		update_limits({ limit : value })

@click.command('clear-limit')
@click.option('--site', help='site name')
@click.argument('limit', type=click.Choice(['emails', 'space', 'users', 'expiry',
	'support_email', 'support_chat', 'upgrade_link']))
@pass_context
def clear_limit(context, site, limit):
	"""Clears given limit from the site config, and removes limit from site config if its empty"""
	from frappe.limits import clear_limit as _clear_limit
	if not site:
		site = get_site(context)

	with frappe.init_site(site):
		_clear_limit(limit)

		# Remove limits from the site_config, if it's empty
		limits = get_limits()
		if not limits:
			update_site_config('limits', 'None', validate=False)


commands = [
	add_system_manager,
	backup,
	drop_site,
	install_app,
	list_apps,
	migrate,
	new_site,
	reinstall,
	reload_doc,
	remove_from_installed_apps,
	restore,
	run_patch,
	set_admin_password,
	uninstall,
	set_limit,
	clear_limit,
	_use,
]
