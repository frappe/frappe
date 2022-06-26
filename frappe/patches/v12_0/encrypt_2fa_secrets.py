import frappe
import frappe.defaults
from frappe.model.naming import make_autoname
from frappe.twofactor import PARENT_FOR_DEFAULTS
from frappe.utils import now_datetime
from frappe.utils.password import encrypt

DOCTYPE = "DefaultValue"
OLD_PARENT = "__default"


def execute():
	table = frappe.qb.DocType(DOCTYPE)

	# set parent for `*_otplogin`
	(
		frappe.qb.update(table)
		.set(table.parent, PARENT_FOR_DEFAULTS)
		.where(table.parent == OLD_PARENT)
		.where(table.defkey.like("%_otplogin"))
	).run()

	# create new encrypted records for `*_otpsecret`
	secrets = {
		key: value
		for key, value in frappe.defaults.get_defaults_for(parent=OLD_PARENT).items()
		if key.endswith("_otpsecret")
	}

	fields = (
		"name",
		"creation",
		"modified",
		"modified_by",
		"owner",
		"parent",
		"parenttype",
		"parentfield",
		"defkey",
		"defvalue",
	)

	user = frappe.session.user
	now = str(now_datetime())

	values = [
		(
			make_autoname("hash", DOCTYPE),
			now,
			now,
			user,
			user,
			PARENT_FOR_DEFAULTS,
			"__default",
			"system_defaults",
			key,
			encrypt(value),
		)
		for key, value in secrets.items()
	]

	frappe.db.bulk_insert(DOCTYPE, fields, values)

	frappe.db.delete(
		DOCTYPE,
		{
			"defkey": ("in", list(secrets)),
			"parent": OLD_PARENT,
		},
	)
