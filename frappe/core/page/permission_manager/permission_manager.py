# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


import frappe
import frappe.defaults
from frappe import _
from frappe.core.doctype.doctype.doctype import (
	clear_permissions_cache,
	validate_permissions_for_doctype,
)
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.exceptions import DoesNotExistError
from frappe.modules.import_file import get_file_path, read_doc_from_file
from frappe.permissions import (
	AUTOMATIC_ROLES,
	add_permission,
	get_all_perms,
	get_linked_doctypes,
	reset_perms,
	setup_custom_perms,
	update_permission_property,
)
from frappe.utils import cint
from frappe.utils.user import get_users_with_role as _get_user_with_role

not_allowed_in_permission_manager = ["DocType", "Patch Log", "Module Def"]

# `get_roles_and_doctypes`, `get_permissions`, `add`, `update`, `remove`, `reset`, `get_users_with_role`, `get_standard_permissions`, `get_permission_logs` moved to frappe.core.api.permissions.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_PERMISSIONS_API = {
	"get_roles_and_doctypes": "get_roles_and_doctypes",
	"get_permissions": "get_permissions",
	"add": "add_permission_rule",
	"update": "update_permission_rule",
	"remove": "remove_permission_rule",
	"reset": "reset_permissions",
	"get_users_with_role": "get_users_with_role",
	"get_standard_permissions": "get_standard_permissions",
	"get_permission_logs": "get_permission_logs",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_PERMISSIONS_API.get(name):
		from frappe.core.api import permissions

		return getattr(permissions, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
