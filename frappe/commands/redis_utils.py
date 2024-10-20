import os

import click

import frappe
from frappe.commands import pass_context
from frappe.utils.bench_helper import CliCtxObj


@click.command("create-rq-users")
@click.option(
	"--set-admin-password",
	is_flag=True,
	default=False,
	help="Set new Redis admin(default user) password",
)
@click.option("--use-rq-auth", is_flag=True, default=False, help="Enable Redis authentication for sites")
@pass_context
def create_rq_users(context: CliCtxObj, set_admin_password=False, use_rq_auth=False):
	"""Create Redis Queue users and add to acl and app configs.

	acl config file will be used by redis server while starting the server
	and app config is used by app while connecting to redis server.
	"""
	from frappe.installer import update_site_config
	from frappe.utils.redis_queue import RedisQueue

	run = context.bench.run
	sites = context.bench.sites

	acl_file_path = run.path.joinpath("redis_queue.acl")

	# with frappe.init_site():
	frappe.init(sites.site)
	acl_list, user_credentials = RedisQueue.gen_acl_list(set_admin_password=set_admin_password)

	acl_file_path.write_text("\n".join(acl_list))

	sites.update_config(
		{
			"rq_username": user_credentials["bench"][0],
			"rq_password": user_credentials["bench"][1],
			"use_rq_auth": use_rq_auth,
		}
	)

	click.secho(
		"* ACL and site configs are updated with new user credentials. "
		"Please restart Redis Queue server to enable namespaces.",
		fg="green",
	)

	if set_admin_password:
		env_key = "RQ_ADMIN_PASWORD"
		click.secho(
			"* Redis admin password is successfully set up. "
			"Include below line in .bashrc file for system to use",
			fg="green",
		)
		click.secho(f"`export {env_key}={user_credentials['default'][1]}`")
		click.secho(
			"NOTE: Please save the admin password as you " "can not access redis server without the password",
			fg="yellow",
		)


commands = [create_rq_users]
