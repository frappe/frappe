import os

import click

import frappe


@click.command("create-rq-users")
@click.option(
	"--set-admin-password",
	is_flag=True,
	default=False,
	help="Set new Redis admin(default user) password",
)
@click.option("--use-rq-auth", is_flag=True, default=False, help="Enable Redis authentication for sites")
def create_rq_users(set_admin_password=False, use_rq_auth=False):
	"""Create Redis Queue users and add to acl and app configs.

	acl config file will be used by redis server while starting the server
	and app config is used by app while connecting to redis server.
	"""
	from frappe.installer import update_site_config
	from frappe.utils.redis_queue import RedisQueue

	acl_file_path = os.path.abspath("../config/redis_queue.acl")

	with frappe.init_site():
		acl_list, user_credentials = RedisQueue.gen_acl_list(set_admin_password=set_admin_password)

	with open(acl_file_path, "w") as f:
		f.writelines([acl + "\n" for acl in acl_list])

	sites_path = os.getcwd()
	common_site_config_path = os.path.join(sites_path, "common_site_config.json")
	update_site_config(
		"rq_username",
		user_credentials["bench"][0],
		validate=False,
		site_config_path=common_site_config_path,
	)
	update_site_config(
		"rq_password",
		user_credentials["bench"][1],
		validate=False,
		site_config_path=common_site_config_path,
	)
	update_site_config("use_rq_auth", use_rq_auth, validate=False, site_config_path=common_site_config_path)

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
