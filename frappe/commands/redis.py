import sys
import os

import click
import redis

import frappe
from frappe.utils.rq import RedisQueue
from frappe.utils import get_site_id
from frappe.commands import pass_context, get_site
from frappe.installer import update_site_config

@click.command('add-rq-user')
@click.option('--site', help='site name')
@click.option('-u', '--admin-username', default='default', help='Redis ACL user who can create other users')
@click.option('-p', '--admin-password', default=None, help='Redis user password')
@pass_context
def add_rq_user(context, site=None, admin_username=None, admin_password=None):
	"""Add or update(if exists) Redis Queue user.
	"""
	site = site or get_site(context)
	if site not in frappe.utils.get_sites():
		click.secho(f'Site {site} does not exist!', fg='yellow')
		sys.exit(1)

	with frappe.init_site(site):
		try:
			env_key = 'RQ_ADMIN_PASWORD'
			password = admin_password or os.environ.get(env_key)
			conn = RedisQueue.new(username=admin_username, password=password)
		except:
			msg = f"Please make sure that admin credentials are correct and Redis server runs @ {frappe.local.conf.redis_queue}"
			click.secho(msg, fg='red')
			sys.exit(1)

		user = conn.add_user(username=get_site_id())
		if user:
			update_site_config("rq_password", user.passwords[1:])
		else:
			click.secho("Failed to create ACL user for Redis Queue, please try again.", fg='yellow')
			sys.exit(1)

@click.command('sync-rq-user')
@click.option('--site', help='site name')
@click.option('-u', '--admin-username', default='default', help='Redis ACL user who can create other users')
@click.option('-p', '--admin-password', default=None, help='Redis user password')
@pass_context
def sync_rq_user(context, site=None, admin_username=None, admin_password=None):
	"""Sync Existing system user to Redis Queue.
	"""
	site = site or get_site(context)
	if site not in frappe.utils.get_sites():
		click.secho(f'Site {site} does not exist!', fg='yellow')
		sys.exit(1)

	with frappe.init_site(site):
		site_rq_user_password = frappe.get_site_config().rq_password
		try:
			env_key = 'RQ_ADMIN_PASWORD'
			password = admin_password or os.environ.get(env_key)
			conn = RedisQueue.new(username=admin_username, password=password)
		except:
			msg = f"Please make sure that admin credentials are correct and Redis server runs @ {frappe.local.conf.redis_queue}"
			click.secho(msg, fg='red')
			sys.exit(1)

		user = conn.add_user(username=get_site_id(), password=site_rq_user_password)
		if user:
			update_site_config("rq_password", user.passwords[1:])
			if not site_rq_user_password:
				click.echo(
					f'New password created for user {site} instead of syncing as password does not exist already.')
			else:
				click.echo("Syncing Redis queue user is successful.")
		else:
			click.secho("Failed to create ACL user for Redis Queue, please try again.", fg='yellow')
			sys.exit(1)


@click.command('set-rq-admin-password')
@click.option('--cur-admin-password', default=None, help='Current Redis admin(default user) password')
@click.option('-p', '--new-admin-password', default=None, help='New Redis admin(default user) password')
@click.option('--reset-passwords', is_flag=True, default=False, help='Remove all existing passwords')
def set_rq_admin_password(cur_admin_password=None, new_admin_password=None, reset_passwords=False):
	"""
	Note: This need to be run on an RQ server where password is not set for `default` user.
	"""
	env_key = 'RQ_ADMIN_PASWORD'

	with frappe.init_site():
		cur_password = cur_admin_password or os.environ.get(env_key)
		try:
			password = RedisQueue.set_admin_password(
				cur_password=cur_password, new_password=new_admin_password, reset_passwords=reset_passwords
			)
		except:
			msg = f"Please make sure that admin credentials are correct and Redis server runs @ {frappe.local.conf.redis_queue}"
			click.secho(msg, fg='red')
			sys.exit(1)

	click.secho('Redis admin password is successfully set up. Include below line in .bashrc file for system to use',
		fg='green')
	click.secho(f'`export {env_key}={password}`')
	click.secho('NOTE: Please save the admin password as you can not access redis server without the password', fg='yellow')

# def create_rq_users_for_all_sites(self):
# 	pass


commands = [
	add_rq_user,
	sync_rq_user,
	set_rq_admin_password
]
