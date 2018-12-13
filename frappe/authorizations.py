# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
from six import string_types
import frappe, copy, json
from frappe import _, msgprint
from frappe.utils import cint
import frappe.share
import operator

rights_map = {"read": '11', "print": '12', "email": '13', "export": '14', "report": '15', "share": '16',
              "create": '21', "write": '22', "delete": '23', "amend": '24', "cancel": '25', "import": '26', "submit": '27'}

"""refactor user permission system
core concept:requested authorizations(the doc) against assigned authorizations by multi auth objs
How it works
1. Design: define requested authorization check, which fields to be checked
  1.1 define authorization objects, select fields for authorization check      
	    1.1.1 special auth field: act, corresponding to user operation on the doc, such as New,change, delete, cancel etc
	    1.1.2 optionally add other to be auth checked fields, multi fields can be assigned per auth object
	    1.1.3 combine multi fields by "|" (OR), e.g owner|approver means user can check leave applications which he is owner or approver
            1.1.4 combine multi fields by "." (subfield), e.g customer.customer_group restricts sales order by customer's customer group
  1.2 assign authorizaiton objects to doctype
    1.2.1 common authorization object s_doctype with two auth fields: act and s_doctype is implicitly assigned to all doctypes
    1.2.2 multi auth objects can be assigned to same doctype
    1.2.3 mandatory: if checked, authorization records for this auth object is mandatory for user to access docs of this doctype,
          if not checked, users without authorization records for this auth obj can access the docs if authorized by common
          object s_doctype
  1.3 assigned authorization object to doctype field(optional), for protecting sensitive fields in the doctype
    1.3.1 only one authorization object can be assigned per doctype field
    1.3.2 same authorization object can be assigned to different doctype field under the same doctype
    1.3.3 currently only applicable to get_doc in frappe.desk.form, if not authorized, the field content will be reset to None

2. Manage: assign authorizations(authorized values for the to-be checked fields)
  2.1 maintain authorizations for the role
	  2.1.1 select auth object, select auth field, assign authorized values to the authorization field
	  2.1.2 authorized value rules
		  2.1.2.1 wild card *, which means full authorization on this field
		  2.1.2.2 single fixed value
		  2.1.2.3 single partial fixed value combined with wildcard, e.g Task*
		  2.1.2.4 single variable value link to user master field, using $user. as prefix
		  2.1.2.5 single fixed value for field with descendants, which means it includes all its descendants
		  2.1.2.6 fixed value with range, value from and value to
	  2.1.3 authorizations/authorization ID: each authorization(authorized value for all auth fields in the auth object
    is identified by the authorization ID), Multi auth IDs allowed per auth object in the same role    
 2.2 assign roles to user
	2.2.1 multi roles can be assigned to same user
  2.2.2 final authorizations for the user is derived from authorization records of all assigned roles
  2.2.3 there maybe duplicate records per authorization object for the user

3. Run time checking logic  
	3.1 bypass auth check if ignore_permission is set or user is Administrator
	3.2 auth check is auto triggerred when user do operation(action) on the target document
		3.2.1 implicit check the relevant doc field by the assigned authorization object
	3.3 auth check is auto triggerred when implicitely call db_query.build_match_conditions for listing/report view, fetch for 
    link field etc, system converts user's authorized values (authorizations) as filtering condition and append to SQL where clause

Use cases:
1. user can display/edit leave applications which he/her is the owner or approver
Solution: 1. define auth obj with owner|approver as auth field,   2. assign auth obj to leave application doctype
          3. maintain $user.name as authorized value to the role  4. assign role to user

2. sales user can display/edit only customers which he is the assigned sales person
Solution: 1. define auth obj with sales person as auth field,       2. assign it to customer doctype,
          3. maintain $user.name as authorized value to the role,   4. assign role to user

3. sales user can display/change only sales transactions for customer which he is the assigned sales person
Solution: 1.define auth obj with customer.sales_person as auth field    2. assign auth obj to sales order doctype
          3.when maintain authorized values in role, assign $user.name to auth field customer.sales_person
          4.assign role to user

4. stock user can create/change/display stock entries of Move-In type, can display stock entries of all types
solution: 1. define auth obj with type as auth field,   2. assign auth obj to stock entry doctype
          2. create following 2 authorizations/auth ID in the role for the same auth obj,
             auth ID: 1, act field: create and change, type: Move-In
             auth ID: 2, act field: display,           type: *
"""


def get_docfield_auth_objs(doctype):
    """authorization objects assigned to docfield of the doctype, used for field level auth check """
    auth_key = 'get_docfield_auth_objs|%s' % doctype
    return frappe.cache().hget('auth_objs', auth_key, lambda: _get_docfield_auth_objs(doctype))

def _get_docfield_auth_objs(doctype):
    """authorization objects assigned to docfield of the doctype, used for field level auth check """
    sql = """ select authorization_object, fieldname from tabDocField
		where authorization_object is not Null and
		parent = %s order by authorization_object """
    result = frappe.db.sql(sql, doctype)
    return result

def validate_auth_field(doctype, auth_obj):
    meta = frappe.get_meta(doctype)
    if isinstance(auth_obj, string_types):
        auth_obj = frappe.get_doc('Authorization Object', auth_obj)
    result = []
    for auth_field_rec in auth_obj.get('auth_field'):
        auth_field = auth_field_rec.fieldname
        if auth_field != 'act':
            if '|' in auth_field:
                for field in auth_field.split('|'):
                    check = meta.has_field(field) or field == 'owner'
                    if not check:
                        result.append(field)
                check = True
            elif '.' in auth_field:
                link_field, sub_field = auth_field.split('.', 1)
                if not meta.has_field(link_field):
                    check = False
                    invalid_field = link_field
                else:
                    link_doctype = meta.get_link_doctype(link_field)
                    if link_doctype:
                        check = frappe.get_meta(link_doctype).has_field(sub_field)
                        invalid_field = sub_field
                    else:
                        check = False
                        invalid_field = link_field
            else:
                check = meta.has_field(auth_field)
                invalid_field = auth_field
            if not check and invalid_field != 'owner':
                result.append(invalid_field)
    return result

def get_auth_objs(doctype, auth_obj=None):
    auth_key = 'get_auth_objs|%s|%s' % ('auth_obj' if auth_obj else 'doctype', auth_obj or doctype)
    return frappe.cache().hget('auth_objs', auth_key, lambda: _get_auth_objs(doctype, auth_obj))

def _get_auth_objs(doctype, auth_obj=0):
    if auth_obj:
        sql = """ select distinct auth_obj.name, auth_field.fieldname, 1 from `tabAuthorization Object` auth_obj
						inner join `tabAuthorization Field` auth_field on auth_obj.name = auth_field.parent
					where auth_obj.name = %s"""

    else:
        sql = """ select auth_obj.name, auth_field.fieldname, doctype.mandatory from `tabDoctype Authorization Object` doctype 
			inner join `tabAuthorization Object` auth_obj on doctype.authorization_object = auth_obj.name 
			inner join `tabAuthorization Field` auth_field on auth_obj.name = auth_field.parent
			where doctype.parent = %s order by auth_obj.name"""
    result = frappe.db.sql(sql, auth_obj or doctype)
    return result

def get_user_authorizations(user=None):
    if not user: user = frappe.session.user
    user_authorizations = frappe.cache().hget('user:'+user, 'get_user_authorizations', lambda: _get_user_authorizations(user))
    return user_authorizations

def _get_user_authorizations(user=None):
    if not user: user = frappe.session.user
    sql = """select concat(auth.parent,'-',auth.authorization_object,':',auth.authorization_id),
        auth.authorization_object,auth.auth_field,auth.value_from,auth.value_to,auth.parent
        from `tabHas Role` role inner join `tabRole Authorization` auth on 
        role.role = auth.parent  where role.parent = %s and auth.auth_field is not Null order by 1, 3"""
    result = frappe.db.sql(sql, user)
    return result

def get_authorizations(doctype, act='11', user=None, usage='doc', auth_obj=None):
    if not user: user = frappe.session.user
    act = rights_map.get(act) if act in rights_map.keys() else act
    auth_key = 'get_authorizations|%s|%s|%s|%s' % (doctype, act, usage, auth_obj or '')
    return frappe.cache().hget('user:'+user, auth_key, lambda: _get_authorizations(doctype, act, user, usage, auth_obj=auth_obj))

def _get_authorizations(doctype, act='11', user=None, usage='doc', auth_obj=None):
    """get authorization records list for the doctype
        0. auth records to be ordered by auth obj, auth ID and auth field
        from operator import itemgetter
        sorted_list = sorted(list_to_sort, key=itemgetter(2,0,1))
        1. usage
            1.1 doctype, returns records which auth field is act,
            1.2 doc: return records which auth field is not act, duplicate records removed, records with wildcard(*)  overwrite others
            1.3 match: fetch records which auth field is not act, duplicate records removed,
                if exists wildcard(*) records,  retrun empty list
        2. auth_obj: get auth records for specified auth obj, for auth obj assigned to field
    """
    authorizations = get_user_authorizations(user)
    auth_objs = [j[0] for j in get_auth_objs(doctype, auth_obj)]
    auth_ids = [auth[0] for auth in authorizations if auth[2] == 'act' and auth[1] in auth_objs
                and (auth[3] in [act, '*'] or auth[3] <= act <= auth[4] or match(auth[3], act))]

    if usage in ['doctype','doc']:	# consider the common auth obj s_doctype
        auth_ids_s = [auth[0] for auth in authorizations if auth[2] == 'act' and auth[1] == 's_doctype'
            and (auth[3] in [act, '*'] or auth[3] <= act <= auth[4] or match(auth[3], act))]
        auth_ids_s = [rec[0] for rec in authorizations if rec[0] in auth_ids_s and  rec[1] == 's_doctype'
            and rec[2]  != 'act'  and check_field('DocType', 'name', doctype, rec[3], rec[4], user)]
        auth_ids.extend(auth_ids_s)
    if not auth_ids:
        return []
    auths_act = [i for i in authorizations if i[0] in auth_ids and i[2] == 'act']  # act records
    if usage == 'doctype':        
        return auths_act
    else:
        auths = [i for i in authorizations if i[0] in auth_ids and i[2] != 'act']  # non act records

    #if not auths and usage == 'doc':
    #    return True
    existing_auth = {}  # auth rec without ID field to check duplicate auth records
    auth_id, auth_obj, auth_exclude_id, result = [], [], [], []
    id_wildcard, obj_wildcard = False, False
    count = len(auths)
    for i in range(count):
        if not obj_wildcard:  # bypass following auth ID records of the same auth obj
            auth_id.append(auths[i])
            auth_exclude_id.append(auths[i][1:])
            id_wildcard = True if auths[i][3] == '*' else False
            next_auth_id = auths[i + 1][0] if i < count - 1 else ''
            if auths[i][0] != next_auth_id:
                auth_exclude_id_str = repr(auth_exclude_id)
                if auth_exclude_id_str not in existing_auth.keys():
                    existing_auth.update({auth_exclude_id_str: 1})
                    auth_obj.extend(auth_id)
                if id_wildcard:
                    obj_wildcard = True
                    auth_obj = auth_id  # wildcard auth records overwrite others
                # id_wildcard = False
                auth_id = []
                auth_exclude_id = []
        next_auth_obj = auths[i + 1][1] if i < count - 1 else ''
        if auths[i][1] != next_auth_obj:
            if (usage == 'match' and not obj_wildcard) or usage == 'doc':
                result.extend(auth_obj)
            obj_wildcard = False
            auth_obj = []
            existing_auth = {}
    if usage != 'match' and auths_act:	  # add back the act records for authorization check log 
            result.extend(auths_act)
    return result


def get_auth_key(act, doc='', doctype='', auth_obj=None, as_list=None):
    """ for doctype: dcotype:act
        for doc: doctype:field1:field2:act
        as_list: return authorization check log's doc field child table for insert()
    """
    if not doc and not doctype:
        return ''
    if not doc:
        return '%s|%s' % (doctype, act)
    else:
        doc_for_auth = {}
        recs = []
        for (auth_obj, auth_field, _) in get_auth_objs(doc.doctype, auth_obj):
            if auth_field != 'act' and auth_field not in doc_for_auth:
                field_value = ''
                if '|' in auth_field:
                    if as_list:
                        for field in auth_field.split('|'):
                            recs.append({'auth_obj': auth_obj,
                                         'auth_field': field,
                                         'value': doc.get(field)})
                    else:
                        field_value = '|'.join(['%s:%s' % (field, doc.get(field)) for field in auth_field.split('|')])
                elif '.' in auth_field:
                    link_field, sub_field = auth_field.split('.', 1)
                    link_doctype = frappe.get_meta(doc.doctype).get_link_doctype(link_field)
                    link_doc_name = doc.get(link_field)
                    value = frappe.get_doc(link_doctype, link_doc_name).get(sub_field)
                    if as_list:
                        recs.append({'auth_obj': auth_obj,
                                     'auth_field': auth_field,
                                     'value': value})
                    else:
                        field_value = '%s:%s' % (auth_field, value)
                else:
                    if as_list:
                        recs.append({'auth_obj': auth_obj,
                                     'auth_field': auth_field,
                                     'value': doc.get(auth_field)})
                    else:
                        field_value = '%s:%s' % (auth_field, doc.get(auth_field))
                doc_for_auth[auth_field] = field_value or ''
        if as_list:
            auth_key = recs
        else:
            auth_key = '%s|%s|%s' % (doc.get('doctype'), '|'.join(doc_for_auth.values()), act)
    return auth_key

def get_descendants(doctype, field, field_value):
    """ support using parent value on the value from """
    f = frappe.get_meta(doctype).get_field(field)
    if f and f.fieldtype == 'Link' and frappe.get_meta(f.options).is_nested_set():
        return frappe.db.get_descendants(f.options, field_value)

def get_doc_name(doc):
	if not doc: return None
	return doc if isinstance(doc, string_types) else doc.name

def auth_check(doctype=None, act='read', doc=None, user=None, auth_obj=None, verbose=1):
    if not user: user = frappe.session.user
    if user=="Administrator" or frappe.flags.in_install:
        if verbose: print("Allowing Administrator")
        return True	
    ptype = act
    act = rights_map.get(act) if act in rights_map.keys() else '11'
    if not doc and hasattr(doctype, 'doctype'):
        # first argument can be doc or doctype
        doc = doctype
        doctype = doc.doctype
    if doc:
        if isinstance(doc, string_types):
            doc = frappe.get_doc(doctype, doc)

    if doc: doctype = doc.get('doctype')
    if not doctype:
        return False
    auth_key = get_auth_key(act, doc, doctype, auth_obj)
    auth_key = 'auth_check|%s' % auth_key
    result = frappe.cache().hget('user:'+user, auth_key,
        lambda: _auth_check(doctype=doctype, act=act, doc=doc, user=user, auth_obj=auth_obj, verbose=verbose))

    def false_if_not_shared():
        if ptype in ("read", "write", "share", "email", "print"):
            shared = frappe.share.get_shared(doctype, user,
                ["read" if ptype in ("email", "print") else ptype])

            if doc:
                doc_name = get_doc_name(doc)
                if doc_name in shared:
                    if verbose: print("Shared")
                    if ptype in ("read", "write", "share") or meta.permissions[0].get(ptype):
                        if verbose: print("Is shared")
                        return True
            elif shared:
                # if atleast one shared doc of that type, then return True
                # this is used in db_query to check if permission on DocType
                if verbose: print("Has a shared document")
                return True
        if verbose: print("Not Shared")
        return False

    if not result and ptype in ("read", "write", "share", "email", "print"):
        result = false_if_not_shared()
    if not result: print('auth_check failure, user=', user, 'act=', act, 'doctype=', doctype)
    return result

def match(first, second):
    """# Python program to match wild card characters
	# The main function that checks if two given strings match.
	# The first string may contain wildcard characters
	"""
    # If we reach at the end of both strings, we are done
    if len(first) == 0 and len(second) == 0:
        return True

    # Make sure that the characters after '*' are present
    # in second string. This function assumes that the first
    # string will not contain two consecutive '*'
    if len(first) > 1 and first[0] == '*' and len(second) == 0:
        return False

    # If the first string contains '?', or current characters
    # of both strings match
    first, second = str(first), str(second)
    if (len(first) > 1 and first[0] == '?') or (len(first) != 0
                                                and len(second) != 0 and first[0] == second[0]):
        return match(first[1:], second[1:])

    # If there is *, then there are two possibilities
    # a) We consider current character of second string
    # b) We ignore current character of second string.
    if len(first) != 0 and first[0] == '*':
        return match(first[1:], second) or match(first, second[1:])

    return False

def check_field(doctype, field, field_value, value_from, value_to=None, user=None):
    """ checking doc field against user's assigned authorizations(via role): value from/value to
		1. wildcard * matches all
		2. wildcard as part of the text, works as like % in SQL
		3. variable field from user master, $user.company, will substitue with current user master field
		4. value from and value to,  works as between(inclusive) in SQL
		5. simple value, works as equal(=) in SQL
		6. for field support hierarchy structure, the descedants included
		7. mutli fields separated by | is treated as OR
	"""
    if value_from == '*':
        return True
    if not value_to:
        if any(c in value_from for c in ['*', '?']):
            return match(value_from, field_value)
        else:  # to do handle get descendant
            if '$user.' in value_from:
                value_from = frappe.get_doc('User', user).get(value_from.split('.')[1])            
            if '|' in field:  # owner|approver multi fields combined by OR logic
                return value_from in field_value

            if field_value == value_from:
                return True
            else:
                descendants = get_descendants(doctype, field, value_from)
                return field_value in descendants if descendants else False
    else:
        return value_from <= field_value <= value_to

def _auth_check(doctype=None, act='read', doc=None, user=None, auth_obj=None, verbose=1):
    """1.doctype level check:only act field is relevant
       2.doc level check:
            2.1 at least one valid auth records exists, to support adding more auth objs later for new user only,
             no impact to existing users without authorizations for new auth obj
            2.2 for doc field with empty value, check is OK
            2.3 Logic of combining all relevant authorizations per each authorizationID
                2.3.1 same authorizationID, same auth obj,different auth field: AND
                2.3.2 different authorizationID, same auth obj: OR
                2.3.3 different authorizationID, different auth obj: AND
                2.3.4 field level auth check: refer to check field documentation
    """
    if not user: user = frappe.session.user
    check_log = {'doc_type': doctype, 'doctype': 'Authorization Check Log', 'act': act}
    if doc:
        check_log['doc_name'] = doc.get('name')
    if verbose: print('_auth_check parameter:%s:%s:%s:%s:%s' % (doctype, act, doc, user, auth_obj))
    result = []
    auth_objs = get_auth_objs(doctype, auth_obj)
    if verbose: print('auth check, auth_objs:', auth_objs)
    if not doc and not auth_obj:  # doctype level check
        auths = get_authorizations(doctype, act, user, usage='doctype')
        if verbose: print('auth_check,by doctype, auths:', auths)
        if not auths:
            check_log['reason'] = 'no valid authorizations record for s_doctype'
            auth_obj_recs = [['s_doctype', 's_doctype']]
            save_check_log(check_log, user, auth_obj_recs)
            return False
        mandatory_objs = [obj for obj in auth_objs or [] if obj[2]]
        mandatory_auths = bool([a for a in auths or [] if a[2] in mandatory_objs]) if mandatory_objs else True 
        if not mandatory_auths:
            check_log['reason'] = 'no authorizations record for mandatory auth objs'
            save_check_log(check_log, user, mandatory_auth_objs)
            return False
        return True
    else:
        auths = get_authorizations(doctype, act, user, usage='doc', auth_obj=auth_obj)
        if not auths:
            auth_obj_recs = list(auth_objs)
            auth_obj_recs.append(['s_doctype', 's_doctype'])		
            check_log['reason'] = 'no valid authorizations for doc'
            save_check_log(check_log, user, auth_obj_recs, doc)
            if verbose: print('auth check, no authorizations')
            return False
        if verbose: print('auth check doc or auth obj auths:', auths, 'doctype:', doctype)
        auth_objs = [i for i in auth_objs if i[1] != 'act']
        if verbose: print('auth_objs records excludes auth_field=act:', auth_objs)
        if not auth_objs:  # only act auth field defined for the auth obj or common auth obj s_doctype exist
            if verbose: print("Check OK for auth objs with only act auth field, or only auth obj s_doctype")
            return True
        else:
            pre_auth_obj = ''
            for (auth_obj, auth_field, mandatory) in auth_objs:
                # multi auth objs to be checked by AND logic in SQL where clause
                auth_obj_recs = [[auth_obj, auth_field]]
                # check_log.update({'authorization_object': auth_obj, 'authorization_field': auth_field})
                if auth_obj != pre_auth_obj:
                    result = []
                    pre_auth_obj = auth_obj
                    obj_auths = [auth for auth in auths if auth[1] == auth_obj and auth[2] != 'act']
                if not obj_auths:  # handle mandatory or optional auth obj for doctype
                    if mandatory:
                        check_log['reason'] = 'no authorizations for mandatory auth object'
                        save_check_log(check_log, user, auth_obj_recs, doc)
                        return False
                    else:
                        result = True
                        continue
                if '|' in auth_field:
                    check_value = [doc.get(field) for field in auth_field.split('|')]
                elif '.' in auth_field:
                    link_field, sub_field = auth_field.split('.', 1)
                    link_doctype = frappe.get_meta(doctype).get_link_doctype(link_field)
                    link_field_value = doc.get(link_field)
                    check_value = frappe.get_doc(link_doctype, link_field_value).get(sub_field)
                else:
                    check_value = doc.get(auth_field)  # act if auth_field=='act' else
                if not check_value:  # bypass checking empty to be checked doc field
                    auth = [i[0] for i in obj_auths if i[2] == auth_field]
                else:
                    auth = [i[0] for i in obj_auths if
                            i[2] == auth_field and check_field(doctype, auth_field, check_value, i[3], i[4], user)]
                if not auth:
                    if verbose: print('auth_obj:', auth_obj, 'auth_field:', auth_field, 'doc field/check_value:',
                                      check_value, 'authorzied value for auth_obj:', obj_auths)
                    check_log['reason'] = 'not authorized for this auth field'
                    save_check_log(check_log, user, auth_obj_recs, doc)
                    return False
                else:
                    result = set(result) & set(auth) if result else set(auth)
                if not result:
                    if verbose: print('auth check,individual authorization not in same auth ID', result, auth)
                    check_log['reason'] = 'not authorized for multi auth fields'
                    save_check_log(check_log, user, auth_obj_recs, doc)
                    return False
        if verbose: print('_auth_check, result:', result)
        if not bool(result):
            check_log['reason'] = 'not authorized for multi auth objs'
            save_check_log(check_log, user)
    return bool(result)

def save_check_log(check_log, user, auth_obj_recs=None, doc=None):
    if doc:
        auth_doc = get_auth_key('', doc, as_list=1)
    else:
        auth_doc = [{'auth_obj': rec[0], 'auth_field': rec[1]} for rec in auth_obj_recs or []]
    check_log['auth_doc'] = auth_doc
    if auth_obj_recs:
        check_log['authorization_object'] = auth_obj_recs[0][0]
        check_log['authorization_field'] = auth_obj_recs[0][1]
    auth_objs = [rec[0] for rec in auth_obj_recs]
    auths = [auth for auth in get_user_authorizations(user) or [] if auth[1] in auth_objs]
    if auths:
        auths = sorted(auths, key=operator.itemgetter(0))	  # sort by auth_id column for better readability
        fieldname = ['authorization_id', 'authorization_object', 'authorization_field', 'value_from', 'value_to', 'role']
        recs = []
        for auth in (auths or []):
            rec = {}
            for i in range(len(auth)):	# extract concatenated auth ID's ID 
                rec[fieldname[i]] = auth[i].split(':')[-1] if i == 0 else auth[i]
            recs.append(rec)
        check_log['authorizations'] = recs
    auth_check_log = frappe.get_doc(check_log)
    auth_check_log.flags.ignore_links = True	# to improve performance
    frappe.local.rollback_observers.append(auth_check_log)
    old_name = '%s-%s' % (user, check_log.get('doc_type'))
    frappe.delete_doc('Authorization Check Log', old_name, force=1, ignore_permissions=1)
    auth_check_log.insert(ignore_permissions=1)
    
def auth_check_doc_fields(doc, user=None):
    if not user: user = frappe.session.user
    if user=="Administrator" or frappe.flags.in_install:        
        return True	
    auth_objs = get_docfield_auth_objs(doc.doctype)
    prev_auth_obj = ''
    result = True
    auth_check_result = True
    for (auth_obj, fieldname) in auth_objs:
        if auth_obj != prev_auth_obj:
            auth_check_result = auth_check(doc.doctype, 'read', doc, user, auth_obj)
            prev_auth_obj = auth_obj
        if not auth_check_result:
            doc.set(fieldname, None)
            result = False
    return result

def get_match_conditions(doctype, act='read', user=None, tables=[], parent_doctype=None, verbose=None):
    """ apply auth relevant restriction to db_query's where condition, which is called by via get_list/get_all or report query
		for logic details, please check the _auth_check documentation
	tables:[table1,field1,table2,field2,table1_alias,table2_alias] from db_query
	parent_doctype: used for fetching child doctype's match condition to determine correct table alias
	return: where condition, prefixed with table alias, also the tables list, to be used by db_query to build correct join clause
	"""

    def build_condition(auth, table_alias):
        """generate SQL where condition per auth record for single field"""
        auth_field, value_from, value_to = auth[2], auth[3], auth[4]

        if '.' in auth_field:  # get the actual field name
            auth_field = auth_field.split('.')[-1]
        # add table alias as prefix, considering composite field splitted by |
        auth_field_no_prefix = auth_field
        auth_field = '|'.join(['%s.%s' % (table_alias, i) for i in auth_field.split('|')])
        if value_from and value_to:
            condition = "%s between '%s' and '%s'" % (auth_field, value_from, value_to)
        elif '*' in value_from:
            condition = "%s like '%s'" % (auth_field, value_from.replace('*', '%'))
        else:
            if '$user.' in value_from:
                value_from = frappe.get_doc('User', user).get(value_from.split('.')[1])
            descendants = get_descendants(doctype, auth_field_no_prefix, value_from)
            if not descendants:
                condition = "%s = '%s'" % (auth_field, value_from)
            else:
                condition = "%s in (%s)" % (auth_field, ','.join(["'%s'" % j for j in descendants]))
            # a|b between "c" and "d" => a between "c" and "d" or b between "c" and "d"
        if '|' in auth_field:
            condition_value = condition.replace(auth_field, '')
            condition = ' or '.join(["%s%s" % (k, condition_value) for k in auth_field.split('|')])
        return condition

    if not user: user = frappe.session.user
    if user=="Administrator":
        return ''
    if not parent_doctype:
        parent_doctype = ''
    act = rights_map.get(act) if act in rights_map.keys() else act
    auths = get_authorizations(doctype, act, user, usage='match')
    auth_objs = get_auth_objs(doctype)
    mandatory_auth_objs = [obj for obj in auth_objs or [] if obj[2]]
    mandatory_auths = not mandatory_auth_objs or [auth for auth in auths or [] if auth[2] in mandatory_auth_objs]
    if not mandatory_auths:
        return "( 1 = 2 )"
    if not tables:	# reportview call get match condition without further processing table joins, so subfield can not be processed
        auths = [auth for auth in auths if '.' not in auth[2]]
    if verbose: print('auths:', auths, 'dcotype:', doctype)
    result = ''
    count = len(auths) if auths else 0
    for i in range(count):
        pre_auth_id = auths[i - 1][0] if i > 0 else ''
        pre_auth_obj = auths[i - 1][1] if i > 0 else ''
        pre_auth_field = auths[i - 1][2] if i > 0 else ''
        if auths[i][1] != pre_auth_obj:
            if i == 0:
                result = '('
            else:
                result += ' and ('
        else:
            if auths[i][0] != pre_auth_id:
                result += ' or '
        if auths[i][0] != pre_auth_id:
            result += '('
        else:
            if auths[i][2] != pre_auth_field:
                result += ' and '
            else:
                result += ' or '
        if auths[i][2] != pre_auth_field:
            result += '('
        auth_field = auths[i][2]
        table2_alias = tables[0] if tables else '`tab%s`' % doctype
        if parent_doctype:  # make sure child table already joined
            child_table = [j for j in tables if j[2] == '`tab%s`' % doctype]
            if child_table:
                table2_alias = child_table[0][5]
            else:
                table1 = "`tab%s`" % parent_doctype
                table2_alias = '`%s_%s`' % (parent_doctype, auth_field.split('.', 1)[0])
                table = [table1, "name", "`tab%s`" % doctype, "parent", table1, table2_alias]
                tables.append(table)
        if '.' in auth_field:  # handle 1 level link field's subfield
            link_field, sub_field = auth_field.split('.', 1)
            link_doctype = frappe.get_meta(doctype).get_link_doctype(link_field)
            link_table_name = "`tab%s`" % link_doctype
            link_table = [k for k in tables if k[2] == link_table_name]
            if link_table:
                table2_alias = link_table[0][5]
            else:
                table1 = "`tab%s`" % doctype
                table1_alias = table2_alias if parent_doctype else table1
                table2_alias = '`%s_%s`' % (doctype, link_field)
                table = [table1, link_field, link_table_name, "name", table1_alias, table2_alias]
                tables.append(table)
        field_condition = build_condition(auths[i], table2_alias)
        if verbose: print('field condition, auth record', auths[i], ',table alias:', table2_alias)
        result += field_condition
        next_auth_id = auths[i + 1][0] if i < count - 1 else ''
        next_auth_obj = auths[i + 1][1] if i < count - 1 else ''
        next_auth_field = auths[i + 1][2] if i < count - 1 else ''
        if auths[i][2] != next_auth_field:
            result += ')'
        if auths[i][0] != next_auth_id:
            result += ')'
        if auths[i][1] != next_auth_obj:
            result += ')'

    if verbose: print('final match condition:', result)
    return result

def can_import(doctype, raise_exception=False):
    if not ("System Manager" in frappe.get_roles() or auth_check(doctype, "import")):
        if raise_exception:
            raise frappe.PermissionError("You are not allowed to import: {doctype}".format(doctype=doctype))
        else:
            return False
    return True

def can_export(doctype, raise_exception=False):
    if not ("System Manager" in frappe.get_roles() or auth_check(doctype, "export")):
        if raise_exception:
            raise frappe.PermissionError("You are not allowed to export: {doctype}".format(doctype=doctype))
        else:
            return False
    return True

def get_doc_authorizations(doc, verbose=False, user=None, ptype=None):
    """Returns a dict of evaluated permissions for given `doc` like `{"read":1, "write":1}`"""
    if not user: user = frappe.session.user
    if frappe.is_table(doc.doctype): return {"read": 1, "write": 1}
    if not has_controller_permissions(doc, ptype, user=user):
        return {ptype: 0}
    auths = {}
    if ptype:
        auths[ptype] = auth_check('',ptype, doc, verbose=verbose)
    else:
        for k, v in rights_map.items():
            auths[k] = auth_check('', v, doc, verbose=verbose)

    return auths
