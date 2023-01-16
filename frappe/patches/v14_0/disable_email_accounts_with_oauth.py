import click

import frappe


def execute():
	# Setting awaiting password to 1 for email accounts where Oauth is enabled.
	# This is done so that people can resetup their email accounts with connected app mechanism.
	doctype = frappe.qb.DocType("Email Account")
	frappe.qb.update(doctype).set(doctype.awaiting_password, 1).where(doctype.auth_mehtod == "OAuth")

	click.secho(
		"Email Accounts with auth method as OAuth have been disabled."
		"Please re-setup your OAuth based email accounts with the connected app mechanism to re-enable them."
	)
