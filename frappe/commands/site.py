# imports - standard imports
import os
import sys

# imports - third party imports
import click

# imports - module imports
import frappe
from frappe.commands import get_site, pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils import get_site_path, touch_file


@click.command('new-site')
@click.argument('site')
@click.option('--db-name', help='Database name')
@click.option('--db-password', help='Database password')
@click.option('--db-type', default='mariadb', type=click.Choice(['mariadb', 'postgres']), help='Optional "postgres" or "mariadb". Default is "mariadb"')
@click.option('--db-host', help='Database Host')
@click.option('--db-port', type=int, help='Database Port')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--no-mariadb-socket', is_flag=True, default=False, help='Set MariaDB host to % and use TCP/IP Socket instead of using the UNIX Socket')
@click.option('--admin-password', help='Administrator password for new site', default=None)
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
@click.option('--force', help='Force restore if site/database already exists', is_flag=True, default=False)
@click.option('--source_sql', help='Initiate database with a SQL file')
@click.option('--install-app', multiple=True, help='Install app after installation')
def new_site(site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None,
			 verbose=False, install_apps=None, source_sql=None, force=None, no_mariadb_socket=False,
			 install_app=None, db_name=None, db_password=None, db_type=None, db_host=None, db_port=None):
	"Create a new site"
	frappe.init(site=site, new_site=True)

	_new_site(db_name, site, mariadb_root_username=mariadb_root_username,
			  mariadb_root_password=mariadb_root_password, admin_password=admin_password,
			  verbose=verbose, install_apps=install_app, source_sql=source_sql, force=force,
			  no_mariadb_socket=no_mariadb_socket, db_password=db_password, db_type=db_type, db_host=db_host,
			  db_port=db_port, new_site=True)

	if len(frappe.utils.get_sites()) == 1:
		use(site)

def _new_site(db_name, site, mariadb_root_username=None, mariadb_root_password=None,
			  admin_password=None, verbose=False, install_apps=None, source_sql=None, force=False,
			  no_mariadb_socket=False, reinstall=False,  db_password=None, db_type=None, db_host=None,
			  db_port=None, new_site=False):
	"""Install a new Frappe site"""

	if not force and os.path.exists(site):
		print('Site {0} already exists'.format(site))
		sys.exit(1)

	if no_mariadb_socket and not db_type == "mariadb":
		print('--no-mariadb-socket requires db_type to be set to mariadb.')
		sys.exit(1)

	if not db_name:
		import hashlib
		db_name = '_' + hashlib.sha1(site.encode()).hexdigest()[:16]

	from frappe.commands.scheduler import _is_scheduler_enabled
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

	installing = touch_file(get_site_path('locks', 'installing.lock'))

	install_db(root_login=mariadb_root_username, root_password=mariadb_root_password, db_name=db_name,
		admin_password=admin_password, verbose=verbose, source_sql=source_sql, force=force, reinstall=reinstall,
		db_password=db_password, db_type=db_type, db_host=db_host, db_port=db_port, no_mariadb_socket=no_mariadb_socket)
	apps_to_install = ['frappe'] + (frappe.conf.get("install_apps") or []) + (list(install_apps) or [])
	for app in apps_to_install:
		_install_app(app, verbose=verbose, set_as_patched=not source_sql)

	os.remove(installing)

	frappe.utils.scheduler.toggle_scheduler(enable_scheduler)
	frappe.db.commit()

	scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
	print("*** Scheduler is", scheduler_status, "***")


@click.command('restore')
@click.argument('sql-file-path')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--db-name', help='Database name for site in case it is a new one')
@click.option('--admin-password', help='Administrator password for new site')
@click.option('--install-app', multiple=True, help='Install app after installation')
@click.option('--with-public-files', help='Restores the public files of the site, given path to its tar file')
@click.option('--with-private-files', help='Restores the private files of the site, given path to its tar file')
@click.option('--force', is_flag=True, default=False, help='Use a bit of force to get the job done')
@pass_context
def restore(context, sql_file_path, mariadb_root_username=None, mariadb_root_password=None, db_name=None, verbose=None, install_app=None, admin_password=None, force=None, with_public_files=None, with_private_files=None):
	"Restore site database from an sql file"
	from frappe.installer import extract_sql_gzip, extract_files, is_downgrade
	force = context.force or force

	# Extract the gzip file if user has passed *.sql.gz file instead of *.sql file
	if not os.path.exists(sql_file_path):
		base_path = '..'
		sql_file_path = os.path.join(base_path, sql_file_path)
		if not os.path.exists(sql_file_path):
			print('Invalid path {0}'.format(sql_file_path[3:]))
			sys.exit(1)
	elif sql_file_path.startswith(os.sep):
		base_path = os.sep
	else:
		base_path = '.'

	if sql_file_path.endswith('sql.gz'):
		decompressed_file_name = extract_sql_gzip(os.path.abspath(sql_file_path))
	else:
		decompressed_file_name = sql_file_path

	site = get_site(context)
	frappe.init(site=site)

	# dont allow downgrading to older versions of frappe without force
	if not force and is_downgrade(decompressed_file_name, verbose=True):
		warn_message = "This is not recommended and may lead to unexpected behaviour. Do you want to continue anyway?"
		click.confirm(warn_message, abort=True)

	_new_site(frappe.conf.db_name, site, mariadb_root_username=mariadb_root_username,
		mariadb_root_password=mariadb_root_password, admin_password=admin_password,
		verbose=context.verbose, install_apps=install_app, source_sql=decompressed_file_name,
		force=True, db_type=frappe.conf.db_type)

	# Extract public and/or private files to the restored site, if user has given the path
	if with_public_files:
		with_public_files = os.path.join(base_path, with_public_files)
		public = extract_files(site, with_public_files, 'public')
		os.remove(public)

	if with_private_files:
		with_private_files = os.path.join(base_path, with_private_files)
		private = extract_files(site, with_private_files, 'private')
		os.remove(private)

	# Removing temporarily created file
	if decompressed_file_name != sql_file_path:
		os.remove(decompressed_file_name)

	success_message = "Site {0} has been restored{1}".format(site, " with files" if (with_public_files or with_private_files) else "")
	click.secho(success_message, fg="green")

@click.command('reinstall')
@click.option('--admin-password', help='Administrator Password for reinstalled site')
@click.option('--mariadb-root-username', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--yes', is_flag=True, default=False, help='Pass --yes to skip confirmation')
@pass_context
def reinstall(context, admin_password=None, mariadb_root_username=None, mariadb_root_password=None, yes=False):
	"Reinstall site ie. wipe all data and start over"
	site = get_site(context)
	_reinstall(site, admin_password, mariadb_root_username, mariadb_root_password, yes, verbose=context.verbose)

def _reinstall(site, admin_password=None, mariadb_root_username=None, mariadb_root_password=None, yes=False, verbose=False):
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
	_new_site(frappe.conf.db_name, site, verbose=verbose, force=True, reinstall=True, install_apps=installed,
		mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password,
		admin_password=admin_password)

@click.command('install-app')
@click.argument('apps', nargs=-1)
@pass_context
def install_app(context, apps):
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
				_install_app(app, verbose=context.verbose)
			except frappe.IncompatibleApp as err:
				err_msg = ":\n{}".format(err) if str(err) else ""
				print("App {} is Incompatible with Site {}{}".format(app, site, err_msg))
				exit_code = 1
			except Exception as err:
				err_msg = ":\n{}".format(err if str(err) else frappe.get_traceback())
				print("An error occurred while installing {}{}".format(app, err_msg))
				exit_code = 1

		frappe.destroy()

	sys.exit(exit_code)


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
@click.option('--password')
@click.option('--send-welcome-email', default=False, is_flag=True)
@pass_context
def add_system_manager(context, email, first_name, last_name, send_welcome_email, password):
	"Add a new system manager to a site"
	import frappe.utils.user
	for site in context.sites:
		frappe.connect(site=site)
		try:
			frappe.utils.user.add_system_manager(email, first_name, last_name,
				send_welcome_email, password)
			frappe.db.commit()
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError

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
@click.option('--skip-failing', is_flag=True, help="Skip patches that fail to run")
@click.option('--skip-search-index', is_flag=True, help="Skip search indexing for web documents")
@pass_context
def migrate(context, skip_failing=False, skip_search_index=False):
	"Run patches, sync schema and rebuild files/translations"
	import compileall
	import re
	from frappe.migrate import migrate

	for site in context.sites:
		print('Migrating', site)
		frappe.init(site=site)
		frappe.connect()
		try:
			migrate(
				context.verbose,
				skip_failing=skip_failing,
				skip_search_index=skip_search_index
			)
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError

	print("Compiling Python files...")
	compileall.compile_dir('../apps', quiet=1, rx=re.compile('.*node_modules.*'))

@click.command('migrate-to')
@click.argument('frappe_provider')
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
	if not context.sites:
		raise SiteNotSpecifiedError

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
	if not context.sites:
		raise SiteNotSpecifiedError

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
	if not context.sites:
		raise SiteNotSpecifiedError

@click.command('add-to-hosts')
@pass_context
def add_to_hosts(context):
	"Add site to hosts"
	for site in context.sites:
		frappe.commands.popen('echo 127.0.0.1\t{0} | sudo tee -a /etc/hosts'.format(site))
	if not context.sites:
		raise SiteNotSpecifiedError

@click.command('use')
@click.argument('site')
def _use(site, sites_path='.'):
	"Set a default site"
	use(site, sites_path=sites_path)

def use(site, sites_path='.'):
	if os.path.exists(os.path.join(sites_path, site)):
		with open(os.path.join(sites_path,  "currentsite.txt"), "w") as sitefile:
			sitefile.write(site)
		print("Current Site set to {}".format(site))
	else:
		print("Site {} does not exist".format(site))

@click.command('backup')
@click.option('--with-files', default=False, is_flag=True, help="Take backup with files")
@click.option('--backup-path', default=None, help="Set path for saving all the files in this operation")
@click.option('--backup-path-db', default=None, help="Set path for saving database file")
@click.option('--backup-path-files', default=None, help="Set path for saving public file")
@click.option('--backup-path-private-files', default=None, help="Set path for saving private file")
@click.option('--backup-path-conf', default=None, help="Set path for saving config file")
@click.option('--verbose', default=False, is_flag=True, help="Add verbosity")
@click.option('--compress', default=False, is_flag=True, help="Compress private and public files")
@pass_context
def backup(context, with_files=False, backup_path=None, backup_path_db=None, backup_path_files=None,
	backup_path_private_files=None, backup_path_conf=None, verbose=False, compress=False):
	"Backup"
	from frappe.utils.backups import scheduled_backup
	verbose = verbose or context.verbose
	exit_code = 0

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			odb = scheduled_backup(ignore_files=not with_files, backup_path=backup_path, backup_path_db=backup_path_db, backup_path_files=backup_path_files, backup_path_private_files=backup_path_private_files, backup_path_conf=backup_path_conf, force=True, verbose=verbose, compress=compress)
		except Exception:
			click.secho("Backup failed for Site {0}. Database or site_config.json may be corrupted".format(site), fg="red")
			exit_code = 1
			continue
		odb.print_summary()
		click.secho("Backup for Site {0} has been successfully completed{1}".format(site, " with files" if with_files else ""), fg="green")
		frappe.destroy()

	if not context.sites:
		raise SiteNotSpecifiedError

	sys.exit(exit_code)

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
	if not context.sites:
		raise SiteNotSpecifiedError

@click.command('uninstall-app')
@click.argument('app')
@click.option('--yes', '-y', help='To bypass confirmation prompt for uninstalling the app', is_flag=True, default=False, multiple=True)
@click.option('--dry-run', help='List all doctypes that will be deleted', is_flag=True, default=False)
@click.option('--no-backup', help='Do not backup the site', is_flag=True, default=False)
@click.option('--force', help='Force remove app from site', is_flag=True, default=False)
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


@click.command('drop-site')
@click.argument('site')
@click.option('--root-login', default='root')
@click.option('--root-password')
@click.option('--archived-sites-path')
@click.option('--no-backup', is_flag=True, default=False)
@click.option('--force', help='Force drop-site even if an error is encountered', is_flag=True, default=False)
def drop_site(site, root_login='root', root_password=None, archived_sites_path=None, force=False, no_backup=False):
	_drop_site(site, root_login, root_password, archived_sites_path, force, no_backup)


def _drop_site(site, root_login='root', root_password=None, archived_sites_path=None, force=False, no_backup=False):
	"Remove site from database and filesystem"
	from frappe.database import drop_user_and_database
	from frappe.utils.backups import scheduled_backup

	frappe.init(site=site)
	frappe.connect()

	try:
		if not no_backup:
			scheduled_backup(ignore_files=False, force=True)
	except Exception as err:
		if force:
			pass
		else:
			click.echo("="*80)
			click.echo("Error: The operation has stopped because backup of {s}'s database failed.".format(s=site))
			click.echo("Reason: {reason}{sep}".format(reason=str(err), sep="\n"))
			click.echo("Fix the issue and try again.")
			click.echo(
				"Hint: Use 'bench drop-site {s} --force' to force the removal of {s}".format(sep="\n", tab="\t", s=site)
			)
			sys.exit(1)

	drop_user_and_database(frappe.conf.db_name, root_login, root_password)

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
@click.option('--logout-all-sessions', help='Logout from all sessions', is_flag=True, default=False)
@pass_context
def set_admin_password(context, admin_password, logout_all_sessions=False):
	"Set Administrator password for a site"
	import getpass
	from frappe.utils.password import update_password

	for site in context.sites:
		try:
			frappe.init(site=site)

			while not admin_password:
				admin_password = getpass.getpass("Administrator's password for {0}: ".format(site))

			frappe.connect()
			update_password(user='Administrator', pwd=admin_password, logout_all_sessions=logout_all_sessions)
			frappe.db.commit()
			admin_password = None
		finally:
			frappe.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError

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
	if not context.sites:
		raise SiteNotSpecifiedError

@click.command('browse')
@click.argument('site', required=False)
@pass_context
def browse(context, site):
	'''Opens the site on web browser'''
	import webbrowser
	site = context.sites[0] if context.sites else site

	if not site:
		click.echo('''Please provide site name\n\nUsage:\n\tbench browse [site-name]\nor\n\tbench --site [site-name] browse''')
		return

	site = site.lower()

	if site in frappe.utils.get_sites():
		webbrowser.open(frappe.utils.get_site_url(site), new=2)
	else:
		click.echo("\nSite named \033[1m{}\033[0m doesn't exist\n".format(site))


@click.command('start-recording')
@pass_context
def start_recording(context):
	for site in context.sites:
		frappe.init(site=site)
		frappe.recorder.start()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command('stop-recording')
@pass_context
def stop_recording(context):
	for site in context.sites:
		frappe.init(site=site)
		frappe.recorder.stop()
	if not context.sites:
		raise SiteNotSpecifiedError

@click.command('ngrok')
@pass_context
def start_ngrok(context):
	from pyngrok import ngrok

	site = get_site(context)
	frappe.init(site=site)

	port = frappe.conf.http_port or frappe.conf.webserver_port
	public_url = ngrok.connect(port=port, options={
		'host_header': site
	})
	print(f'Public URL: {public_url}')
	print('Inspect logs at http://localhost:4040')

	ngrok_process = ngrok.get_ngrok_process()
	try:
		# Block until CTRL-C or some other terminating event
		ngrok_process.proc.wait()
	except KeyboardInterrupt:
		print("Shutting down server...")
		frappe.destroy()
		ngrok.kill()

@click.command('build-search-index')
@pass_context
def build_search_index(context):
	from frappe.search.website_search import build_index_for_all_routes
	site = get_site(context)
	if not site:
		raise SiteNotSpecifiedError

	print('Building search index for {}'.format(site))
	frappe.init(site=site)
	frappe.connect()
	try:
		build_index_for_all_routes()
	finally:
		frappe.destroy()

commands = [
	add_system_manager,
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
	build_search_index
]
