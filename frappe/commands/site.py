from __future__ import unicode_literals, absolute_import, print_function
import click
import hashlib, os, sys, compileall
import frappe
from frappe import _
from _mysql_exceptions import ProgrammingError
from frappe.commands import pass_context, get_site
from frappe.commands.scheduler import _is_scheduler_enabled
from frappe.limits import update_limits, get_limits
from frappe.installer import update_site_config
from frappe.utils import touch_file, get_site_path
from six import text_type

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
	frappe.init(site=site, new_site=True)

	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password,
			verbose=verbose, install_apps=install_app, source_sql=source_sql, force=force)

	if len(frappe.utils.get_sites()) == 1:
		use(site)

def _new_site(db_name, site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None,
	verbose=False, install_apps=None, source_sql=None,force=False, reinstall=False):
	"""Install a new Frappe site"""

	if not db_name:
		db_name = hashlib.sha1(site.encode()).hexdigest()[:16]

	from frappe.installer import install_db, make_site_dirs
	from frappe.installer import install_app as _install_app
	import frappe.utils.scheduler

	frappe.init(site=site)

	try:
		# enable scheduler post install?
		enable_scheduler = _is_scheduler_enabled()
	except Exception:
		enable_scheduler = False

	make_site_dirs()

	installing = None
	try:
		installing = touch_file(get_site_path('locks', 'installing.lock'))

		install_db(root_login=mariadb_root_username, root_password=mariadb_root_password, db_name=db_name,
			admin_password=admin_password, verbose=verbose, source_sql=source_sql,force=force, reinstall=reinstall)

		apps_to_install = ['frappe'] + (frappe.conf.get("install_apps") or []) + (list(install_apps) or [])
		for app in apps_to_install:
			_install_app(app, verbose=verbose, set_as_patched=not source_sql)

		frappe.utils.scheduler.toggle_scheduler(enable_scheduler)
		frappe.db.commit()

		scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
		print("*** Scheduler is", scheduler_status, "***")

	except frappe.exceptions.ImproperDBConfigurationError:
		_drop_site(site, mariadb_root_username, mariadb_root_password, force=True)

	finally:
		if installing and os.path.exists(installing):
			os.remove(installing)

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

	if not os.path.exists(sql_file_path):
		sql_file_path = '../' + sql_file_path
		if not os.path.exists(sql_file_path):
			print('Invalid path {0}' + sql_file_path[3:])
			sys.exit(1)

	if sql_file_path.endswith('sql.gz'):
		sql_file_path = extract_sql_gzip(os.path.abspath(sql_file_path))

	site = get_site(context)
	frappe.init(site=site)
	_new_site(frappe.conf.db_name, site, mariadb_root_username=mariadb_root_username,
		mariadb_root_password=mariadb_root_password, admin_password=admin_password,
		verbose=context.verbose, install_apps=install_app, source_sql=sql_file_path,
		force=context.force)

	# Extract public and/or private files to the restored site, if user has given the path
	if with_public_files:
		public = extract_tar_files(site, with_public_files, 'public')
		os.remove(public)

	if with_private_files:
		private = extract_tar_files(site, with_private_files, 'private')
		os.remove(private)

@click.command('reinstall')
@click.option('--admin-password', help='Administrator Password for reinstalled site')
@click.option('--yes', is_flag=True, default=False, help='Pass --yes to skip confirmation')
@pass_context
def reinstall(context, admin_password=None, yes=False):
	"Reinstall site ie. wipe all data and start over"
	site = get_site(context)
	_reinstall(site, admin_password, yes, verbose=context.verbose)

def _reinstall(site, admin_password=None, yes=False, verbose=False):
	if not yes:
		click.confirm('This will wipe your database. Are you sure you want to reinstall?', abort=True)
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
	_new_site(frappe.conf.db_name, site, verbose=verbose, force=True, reinstall=True,
		install_apps=installed, admin_password=admin_password)

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
	print("\n".join(frappe.get_installed_apps()))
	frappe.destroy()

@click.command('add-system-manager')
@click.argument('email')
@click.option('--first-name')
@click.option('--last-name')
@click.option('--send-welcome-email', default=False, is_flag=True)
@pass_context
def add_system_manager(context, email, first_name, last_name, send_welcome_email):
	"Add a new system manager to a site"
	import frappe.utils.user
	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.utils.user.add_system_manager(email, first_name, last_name, send_welcome_email)
			frappe.db.commit()
		finally:
			frappe.destroy()


@click.command('disable-user')
@click.argument('email')
@pass_context
def disable_user(context, email):
	site = get_site(context)
	with frappe.init_site(site):
		frappe.connect()
		user = frappe.get_doc("User", email)
		user.enabled = 0
		user.save(ignore_permissions=True)
		frappe.db.commit()


@click.command('migrate')
@click.option('--rebuild-website', help="Rebuild webpages after migration")
@pass_context
def migrate(context, rebuild_website=False):
	"Run patches, sync schema and rebuild files/translations"
	from frappe.migrate import migrate

	for site in context.sites:
		print('Migrating', site)
		frappe.init(site=site)
		frappe.connect()
		try:
			migrate(context.verbose, rebuild_website=rebuild_website)
		finally:
			frappe.destroy()

	compileall.compile_dir('../apps', quiet=1)

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

@click.command('reload-doctype')
@click.argument('doctype')
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
			print("database backup taken -", odb.backup_path_db, "- on", now())
			if with_files:
				print("files backup taken -", odb.backup_path_files, "- on", now())
				print("private files backup taken -", odb.backup_path_private_files, "- on", now())

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
@click.option('--yes', '-y', help='To bypass confirmation prompt for uninstalling the app', is_flag=True, default=False, multiple=True)
@click.option('--dry-run', help='List all doctypes that will be deleted', is_flag=True, default=False)
@pass_context
def uninstall(context, app, dry_run=False, yes=False):
	"Remove app and linked modules from site"
	from frappe.installer import remove_app
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			remove_app(app, dry_run, yes)
		finally:
			frappe.destroy()


@click.command('drop-site')
@click.argument('site')
@click.option('--root-login', default='root')
@click.option('--root-password')
@click.option('--archived-sites-path')
@click.option('--force', help='Force drop-site even if an error is encountered', is_flag=True, default=False)
def drop_site(site, root_login='root', root_password=None, archived_sites_path=None, force=False):
	_drop_site(site, root_login, root_password, archived_sites_path, force)


def _drop_site(site, root_login='root', root_password=None, archived_sites_path=None, force=False):
	"Remove site from database and filesystem"
	from frappe.installer import get_root_connection
	from frappe.model.db_schema import DbManager
	from frappe.utils.backups import scheduled_backup

	frappe.init(site=site)
	frappe.connect()

	try:
		scheduled_backup(ignore_files=False, force=True)
	except ProgrammingError as err:
		if err[0] == 1146:
			if force:
				pass
			else:
				click.echo("="*80)
				click.echo("Error: The operation has stopped because backup of {s}'s database failed.".format(s=site))
				click.echo("Reason: {reason}{sep}".format(reason=err[1], sep="\n"))
				click.echo("Fix the issue and try again.")
				click.echo(
					"Hint: Use 'bench drop-site {s} --force' to force the removal of {s}".format(sep="\n", tab="\t", s=site)
				)
				sys.exit(1)

	db_name = frappe.local.conf.db_name
	frappe.local.db = get_root_connection(root_login, root_password)
	dbman = DbManager(frappe.local.db)
	dbman.delete_user(db_name)
	dbman.drop_database(db_name)

	if not archived_sites_path:
		archived_sites_path = os.path.join(frappe.get_app_path('frappe'), '..', '..', '..', 'archived_sites')

	if not os.path.exists(archived_sites_path):
		os.mkdir(archived_sites_path)

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
@click.argument('limit')
@click.argument('value')
@pass_context
def set_limit(context, site, limit, value):
	"""Sets user / space / email limit for a site"""
	_set_limits(context, site, ((limit, value),))

@click.command('set-limits')
@click.option('--site', help='site name')
@click.option('--limit', 'limits', type=(text_type, text_type), multiple=True)
@pass_context
def set_limits(context, site, limits):
	_set_limits(context, site, limits)

def _set_limits(context, site, limits):
	import datetime

	if not limits:
		return

	if not site:
		site = get_site(context)

	with frappe.init_site(site):
		frappe.connect()
		new_limits = {}
		for limit, value in limits:
			if limit not in ('daily_emails', 'emails', 'space', 'users', 'email_group',
				'expiry', 'support_email', 'support_chat', 'upgrade_url'):
				frappe.throw(_('Invalid limit {0}').format(limit))

			if limit=='expiry' and value:
				try:
					datetime.datetime.strptime(value, '%Y-%m-%d')
				except ValueError:
					raise ValueError("Incorrect data format, should be YYYY-MM-DD")

			elif limit=='space':
				value = float(value)

			elif limit in ('users', 'emails', 'email_group', 'daily_emails'):
				value = int(value)

			new_limits[limit] = value

		update_limits(new_limits)

@click.command('clear-limits')
@click.option('--site', help='site name')
@click.argument('limits', nargs=-1, type=click.Choice(['emails', 'space', 'users', 'email_group',
	'expiry', 'support_email', 'support_chat', 'upgrade_url', 'daily_emails']))
@pass_context
def clear_limits(context, site, limits):
	"""Clears given limit from the site config, and removes limit from site config if its empty"""
	from frappe.limits import clear_limit as _clear_limit
	if not limits:
		return

	if not site:
		site = get_site(context)

	with frappe.init_site(site):
		_clear_limit(limits)

		# Remove limits from the site_config, if it's empty
		limits = get_limits()
		if not limits:
			update_site_config('limits', 'None', validate=False)

@click.command('set-last-active-for-user')
@click.option('--user', help="Setup last active date for user")
@pass_context
def set_last_active_for_user(context, user=None):
	"Set users last active date to current datetime"

	from frappe.core.doctype.user.user import get_system_users
	from frappe.utils.user import set_last_active_to_now

	site = get_site(context)

	with frappe.init_site(site):
		frappe.connect()
		if not user:
			user = get_system_users(limit=1)
			if len(user) > 0:
				user = user[0]
			else:
				return

		set_last_active_to_now(user)
		frappe.db.commit()

@click.command('publish-realtime')
@click.argument('event')
@click.option('--message')
@click.option('--room')
@click.option('--user')
@click.option('--doctype')
@click.option('--docname')
@click.option('--after-commit')
@pass_context
def publish_realtime(context, event, message, room, user, doctype, docname, after_commit):
	"Publish realtime event from bench"
	from frappe import publish_realtime
	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			publish_realtime(event, message=message, room=room, user=user, doctype=doctype, docname=docname,
				after_commit=after_commit)
			frappe.db.commit()
		finally:
			frappe.destroy()

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
	reload_doctype,
	remove_from_installed_apps,
	restore,
	run_patch,
	set_admin_password,
	uninstall,
	set_limit,
	set_limits,
	clear_limits,
	disable_user,
	_use,
	set_last_active_for_user,
	publish_realtime,
]
