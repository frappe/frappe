# Settings saved per user basis
# such as page_limit, filters, last_view

import json
from pydoc import doc

import frappe
from frappe import safe_decode

# dict for mapping the index and index type for the filters of different views
filter_dict = {"doctype": 0, "docfield": 1, "operator": 2, "value": 3}

default_user_setting = {'updated_on': 'Fri Aug 16 2024 12:10:40 GMT-0500', 'last_view': 'List', 'List': {'filters': [], 'sort_by': 'modified', 'sort_order': 'DESC'}, 'Report': {'fields': [['name', 'Quotation'], ['docstatus', 'Quotation'], ['title', 'Quotation'], ['quotation_to', 'Quotation'], ['party_name', 'Quotation'], ['transaction_date', 'Quotation'], ['order_type', 'Quotation'], ['grand_total', 'Quotation'], ['status', 'Quotation'], ['currency', 'Quotation'], ['customer_name', 'Quotation'], ['base_grand_total', 'Quotation'], ['company', 'Quotation'], ['valid_till', 'Quotation']], 'filters': [], 'order_by': '`tabQuotation`.`modified` desc', 'group_by': None, 'add_totals_row': 0}, 'GridView': {'Quotation Item': [{'fieldname': 'qty', 'columns': 1}, {'fieldname': 'item_code', 'columns': 2}, {'fieldname': 'description', 'columns': 3}, {'fieldname': 'rate', 'columns': 2}, {'fieldname': 'amount', 'columns': 2}]}}


def get_user_settings(doctype, for_update=False):
    user_settings = frappe.cache.hget("_user_settings", f"{doctype}::{frappe.session.user}")

    if user_settings is None:
        user_settings = frappe.db.sql(
            """select data from `__UserSettings`
            where `user`=%s and `doctype`=%s""",
            (frappe.session.user, doctype),
        )
        user_settings = user_settings and user_settings[0][0] or "{}"

        if not for_update:
            update_user_settings(doctype, user_settings, True)

    return user_settings or "{}"


def update_user_settings(doctype, user_settings, for_update=False):
	"""update user settings in cache"""

	if for_update:
		current = json.loads(user_settings)
	else:
		current = json.loads(get_user_settings(doctype, for_update=True))

		if isinstance(current, str):
			# corrupt due to old code, remove this in a future release
			current = {}

		current.update(user_settings)

	frappe.cache.hset("_user_settings", f"{doctype}::{frappe.session.user}", json.dumps(current))


def sync_user_settings():
	"""Sync from cache to database (called asynchronously via the browser)"""
	for key, data in frappe.cache.hgetall("_user_settings").items():
		key = safe_decode(key)
		doctype, user = key.split("::")  # WTF?
		frappe.db.multisql(
			{
				"mariadb": """INSERT INTO `__UserSettings`(`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON DUPLICATE key UPDATE `data`=%s""",
				"postgres": """INSERT INTO `__UserSettings` (`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON CONFLICT ("user", "doctype") DO UPDATE SET `data`=%s""",
			},
			(user, doctype, data, data),
			as_dict=1,
		)


@frappe.whitelist()
def save(doctype, user_settings):
	user_settings = json.loads(user_settings or "{}")
	update_user_settings(doctype, user_settings)
	update_user_settings_in_db(doctype,user_settings)
	return user_settings


def update_user_settings_in_db(doctype, user_settings):
    if doctype in ["Quotation", "Sales Invoice"] and doctype and user_settings and user_settings != {} and user_settings != "{}":
        user_session = frappe.session.user

        # Convertir user_settings a JSON si es un diccionario
        if isinstance(user_settings, dict):
            user_settings_json = json.dumps(user_settings)
        else:
            user_settings_json = user_settings

        frappe.db.sql(
            """
            UPDATE `__UserSettings`
            SET data = %(data)s
            WHERE `user` = %(user_session)s
            AND `doctype` = %(doctype)s
            """,
            {
                "data": user_settings_json,
                "user_session": user_session,
                "doctype": doctype
            }
        )

        frappe.cache.hset("_user_settings", f"{doctype}::{frappe.session.user}", user_settings_json)
    else:
        return user_settings


@frappe.whitelist()
def get(doctype):
	return get_user_settings(doctype)


def update_user_settings_data(
	user_setting, fieldname, old, new, condition_fieldname=None, condition_values=None
):
	data = user_setting.get("data")
	if data:
		update = False
		data = json.loads(data)
		for view in ["List", "Gantt", "Kanban", "Calendar", "Image", "Inbox", "Report"]:
			view_settings = data.get(view)
			if view_settings and view_settings.get("filters"):
				view_filters = view_settings.get("filters")
				for view_filter in view_filters:
					if (
						condition_fieldname
						and view_filter[filter_dict[condition_fieldname]] != condition_values
					):
						continue
					if view_filter[filter_dict[fieldname]] == old:
						view_filter[filter_dict[fieldname]] = new
						update = True
		if update:
			frappe.db.sql(
				"update __UserSettings set data=%s where doctype=%s and user=%s",
				(json.dumps(data), user_setting.doctype, user_setting.user),
			)

			# clear that user settings from the redis cache
			frappe.cache.hset("_user_settings", f"{user_setting.doctype}::{user_setting.user}", None)
