# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_roles_and_doctypes():
	return {
		"doctypes": [d[0] for d in webnotes.conn.sql("""select name from `tabDocType` dt where
			ifnull(istable,0)=0 and
			name not in ('DocType', 'Control Panel') and
			exists(select * from `tabDocField` where parent=dt.name)""")],
		"roles": [d[0] for d in webnotes.conn.sql("""select name from tabRole where name not in
			('Guest', 'Administrator')""")]
	}

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_permissions(doctype=None, role=None):
	return webnotes.conn.sql("""select * from tabDocPerm
		where %s%s order by parent, permlevel, role""" % (\
			doctype and (" parent='%s'" % doctype) or "",
			role and ((doctype and " and " or "") + " role='%s'" % role) or "",
			), as_dict=True)
			
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def remove(doctype, name):
	match = webnotes.conn.get_value("DocPerm", name, "`match`")
	
	webnotes.conn.sql("""delete from tabDocPerm where name=%s""", name)
	validate_and_reset(doctype, for_remove=True)
	
	if match:
		webnotes.defaults.clear_cache()

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def add(parent, role, permlevel):
	webnotes.doc(fielddata={
		"doctype":"DocPerm",
		"__islocal": 1,
		"parent": parent,
		"parenttype": "DocType",
		"parentfield": "permissions",
		"role": role,
		"permlevel": permlevel,
		"read": 1
	}).save()
	
	validate_and_reset(parent)

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def update(name, doctype, ptype, value=0):
	webnotes.conn.sql("""update tabDocPerm set `%s`=%s where name=%s"""\
	 	% (ptype, '%s', '%s'), (value, name))
	validate_and_reset(doctype)
	
	if ptype == "read" and webnotes.conn.get_value("DocPerm", name, "`match`"):
		webnotes.defaults.clear_cache()
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def update_match(name, doctype, match=""):
	webnotes.conn.sql("""update tabDocPerm set `match`=%s where name=%s""",
		(match, name))
	validate_and_reset(doctype)
	webnotes.defaults.clear_cache()
	
def validate_and_reset(doctype, for_remove=False):
	from webnotes.core.doctype.doctype.doctype import validate_permissions_for_doctype
	validate_permissions_for_doctype(doctype, for_remove)
	clear_doctype_cache(doctype)
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def reset(doctype):
	webnotes.reset_perms(doctype)
	clear_doctype_cache(doctype)
	webnotes.defaults.clear_cache()

def clear_doctype_cache(doctype):
	webnotes.clear_cache(doctype=doctype)
	for user in webnotes.conn.sql_list("""select distinct tabUserRole.parent from tabUserRole, tabDocPerm 
		where tabDocPerm.parent = %s
		and tabDocPerm.role = tabUserRole.role""", doctype):
		webnotes.clear_cache(user=user)

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_users_with_role(role):
	return [p[0] for p in webnotes.conn.sql("""select distinct tabProfile.name 
		from tabUserRole, tabProfile where 
			tabUserRole.role=%s
			and tabProfile.name != "Administrator"
			and tabUserRole.parent = tabProfile.name
			and ifnull(tabProfile.enabled,0)=1""", role)]
