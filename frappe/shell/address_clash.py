# A new or renamed DocType or module may not take an address a page or another row already has:
# a DocType competes with flat apps' pages, a module with modular apps' pages.

import glob
import os

import click

import frappe
from frappe import _

from .doctypes import slug
from .manifest import bench_relative, page_glob
from .registry import is_modular


class AddressClashError(frappe.ValidationError):
	pass


def page_files(modular: bool) -> dict[str, str]:
	"""`{slug: path}` over the pages of every installed app of one shape, modular or flat."""
	pages = {}
	for app in frappe.get_installed_apps(_ensure_on_bench=True):
		if is_modular(app) != modular:
			continue
		for path in sorted(glob.glob(page_glob(frappe.get_app_path(app)))):
			pages.setdefault(os.path.splitext(os.path.basename(path))[0], path)
	return pages


def clash(doctype: str, name: str, excluded: set[str]) -> str | None:
	"""Why `name` cannot have its address, or None when the address is free."""
	address = slug(name)

	if page := page_files(modular=doctype == "Module Def").get(address):
		return _("{0} {1} would take the address {2}, which the page {3} already uses.").format(
			_(doctype), name, address, bench_relative(page)
		)

	# In LIKE `_` is any one character, so this finds every spelling of the slug.
	filters = {"name": ["like", address.replace("-", "_")]}
	if doctype == "DocType":
		filters["istable"] = 0
	for other in frappe.get_all(doctype, filters=filters, pluck="name"):
		if other not in excluded and slug(other) == address:
			return _("{0} {1} would take the address {2}, which the {0} {3} already uses.").format(
				_(doctype), name, address, other
			)

	return None


def refuse(doctype: str, name: str, excluded: set[str]):
	if not (message := clash(doctype, name, excluded)):
		return

	# Install, migrate and patch write what app code ships, so a clash there is reported, not refused.
	if frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_install:
		frappe.logger("shell").warning(message)
		click.secho(message, fg="yellow")
		return

	frappe.throw(message, exc=AddressClashError, title=_("Address Taken"))


def validate_address(doc, method=None):
	"""Refuse a new DocType or module whose address is taken; a child table has no address."""
	if doc.is_new() and not doc.get("istable"):
		refuse(doc.doctype, doc.name, {doc.name})


def validate_renamed_address(doc, method=None, old=None, new=None, merge=False):
	"""Refuse a rename whose new name's address is taken."""
	if not doc.get("istable"):
		refuse(doc.doctype, new, {old, new})
