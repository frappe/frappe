# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Legacy location of the document API — the endpoints moved to
`frappe.core.api.document`.

The `frappe.client.*` dotted paths are baked into external integrations,
webhooks and tutorials all over the internet, so these aliases are permanent:
they will keep working indefinitely and are never scheduled for removal.
New code should call `frappe.core.api.document.*` instead.
"""

import frappe
from frappe.core.api.document import (
	attach_file,
	bulk_update,
	cancel,
	delete,
	delete_doc,
	get,
	get_count,
	get_doc_permissions,
	get_list,
	get_password,
	get_single_value,
	get_value,
	has_permission,
	insert,
	insert_doc,
	insert_many,
	is_document_amended,
	rename_doc,
	save,
	set_value,
	submit,
	validate_link_and_fetch,
)
from frappe.deprecation_dumpster import get_js as _get_js

get_js = frappe.whitelist()(_get_js)


# `get_time_zone` moved to frappe.core.api.user; alias below keeps the old
# dotted path working.
from frappe.core.api.user import get_time_zone
