import frappe
import json
from frappe.core.page.permission_manager.permission_manager import get_permissions
from frappe.permissions import get_valid_perms, get_linked_doctypes

def execute():
    user_permissions = frappe.get_all('User Permission', fields=['allow', 'name', 'user'])
    # print(user_permissions)
    doctype_map = {}
    for permission in user_permissions:
        doctype_map[permission.name] = get_doctypes_to_skip(permission.allow, permission.user)

    if not doctype_map: return

    for perm_name, doctype_to_skip in doctype_map.items():
        # print(perm_name, len(doctype_to_skip))
        if not doctype_to_skip: continue
        doctype_to_skip = '\n'.join(doctype_to_skip)
        frappe.db.set_value('User Permission', perm_name, 'skip_for_doctype', doctype_to_skip)

user_valid_perm = {}

def get_doctypes_to_skip(doctype, user):
    ''' Returns doctypes to be skipped from user permission check'''
    doctypes_to_skip = []
    valid_perms = []

    if user_valid_perm.get(user):
        valid_perms = user_valid_perm.get(user)
    else:
        valid_perms = get_valid_perms(user=user)
        user_valid_perm[user] = valid_perms

    for perm in valid_perms:
        try:
            if doctype not in get_linked_doctypes(perm.parent): continue
        except:
            continue
        if not perm.apply_user_permission and perm.parent not in doctypes_to_skip:
            doctypes_to_skip.append(perm.parent)
        elif perm.parent not in doctypes_to_skip:
            try:
                user_permission_doctypes = json.loads(perm.user_permission_doctypes or '[]')
            except ValueError:
                user_permission_doctypes = []
            if not user_permission_doctypes:
                continue
            elif doctype not in user_permission_doctypes and perm.parent not in doctypes_to_skip:
                doctypes_to_skip.append(perm.parent)

    return doctypes_to_skip
