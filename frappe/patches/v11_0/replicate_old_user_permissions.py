import frappe
import json
from frappe.permissions import get_valid_perms, get_linked_doctypes

def execute():
    user_permissions = frappe.get_all('User Permission', fields=['allow', 'name', 'user'])

    doctype_to_skip_map = {}

    for permission in user_permissions:
        doctype_to_skip_map[permission.name] = get_doctypes_to_skip(permission.allow, permission.user)

    if not doctype_to_skip_map: return

    for perm_name, doctype_to_skip in doctype_to_skip_map.items():
        if not doctype_to_skip: continue
        doctype_to_skip = '\n'.join(doctype_to_skip)
        frappe.db.set_value('User Permission', perm_name, 'skip_for_doctype', doctype_to_skip)


def get_doctypes_to_skip(doctype, user):
    ''' Returns doctypes to be skipped from user permission check'''
    doctypes_to_skip = []
    valid_perms = get_user_valid_perms(user) or []

    for perm in valid_perms:

        parent_doctype = perm.parent

        try:
            if doctype not in get_linked_doctypes(parent_doctype): continue
        except frappe.DoesNotExistError:
            # if doctype not found (may be due to rename) it should not be considered for skip
            continue

        if not perm.apply_user_permission:
            # add doctype to skip list if any of the perm does not apply user permission
            doctypes_to_skip.append(doctype)

        elif parent_doctype not in doctypes_to_skip:

            user_permission_doctypes = get_user_permission_doctypes(perm)

            # "No doctypes present" indicates that user permission will be applied to each link field
            if not user_permission_doctypes: continue

            elif doctype in user_permission_doctypes: continue

            else: doctypes_to_skip.append(doctype)

    # to remove possible duplicates
    doctypes_to_skip = list(set(doctypes_to_skip))

    return doctypes_to_skip

# store user's valid perms to avoid repeated query
user_valid_perm = {}

def get_user_valid_perms(user):
    if not user_valid_perm.get(user):
        user_valid_perm[user] = get_valid_perms(user=user)
    return user_valid_perm.get(user)

def get_user_permission_doctypes(perm):
    try:
        return json.loads(perm.user_permission_doctypes or '[]')
    except ValueError:
        return []