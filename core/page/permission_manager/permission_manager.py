# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

@webnotes.whitelist()
def get_roles_and_doctypes():
	webnotes.only_for(("System Manager", "Administrator"))
	return {
		"doctypes": [d[0] for d in webnotes.conn.sql("""select name from `tabDocType` dt where
			ifnull(istable,0)=0 and
			name not in ('DocType', 'Control Panel') and
			exists(select * from `tabDocField` where parent=dt.name)""")],
		"roles": [d[0] for d in webnotes.conn.sql("""select name from tabRole where name not in
			('Guest', 'Administrator')""")]
	}

@webnotes.whitelist()
def get_permissions(doctype=None, role=None):
	webnotes.only_for(("System Manager", "Administrator"))
	return webnotes.conn.sql("""select * from tabDocPerm
		where %s%s order by parent, permlevel, role""" % (\
			doctype and (" parent='%s'" % doctype) or "",
			role and ((doctype and " and " or "") + " role='%s'" % role) or "",
			), as_dict=True)
			
@webnotes.whitelist()
def remove(doctype, name):
	webnotes.only_for(("System Manager", "Administrator"))
	match = webnotes.conn.get_value("DocPerm", name, "`match`")
	
	webnotes.conn.sql("""delete from tabDocPerm where name=%s""", name)
	validate_and_reset(doctype, for_remove=True)
	
	if match:
		webnotes.defaults.clear_cache()

@webnotes.whitelist()
def add(parent, role, permlevel):
	webnotes.only_for(("System Manager", "Administrator"))
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

@webnotes.whitelist()
def update(name, doctype, ptype, value=0):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.conn.sql("""update tabDocPerm set `%s`=%s where name=%s"""\
	 	% (ptype, '%s', '%s'), (value, name))
	validate_and_reset(doctype)
	
	if ptype == "read" and webnotes.conn.get_value("DocPerm", name, "`match`"):
		webnotes.defaults.clear_cache()
	
@webnotes.whitelist()
def update_match(name, doctype, match=""):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.conn.sql("""update tabDocPerm set `match`=%s where name=%s""",
		(match, name))
	validate_and_reset(doctype)
	webnotes.defaults.clear_cache()
	
def validate_and_reset(doctype, for_remove=False):
	from core.doctype.doctype.doctype import validate_permissions_for_doctype
	validate_permissions_for_doctype(doctype, for_remove)
	clear_doctype_cache(doctype)
	
@webnotes.whitelist()
def reset(doctype):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.reset_perms(doctype)
	clear_doctype_cache(doctype)
	webnotes.defaults.clear_cache()

def clear_doctype_cache(doctype):
	webnotes.clear_cache(doctype=doctype)
	for user in webnotes.conn.sql_list("""select distinct tabUserRole.parent from tabUserRole, tabDocPerm 
		where tabDocPerm.parent = %s
		and tabDocPerm.role = tabUserRole.role""", doctype):
		webnotes.clear_cache(user=user)

@webnotes.whitelist()
def get_users_with_role(role):
	webnotes.only_for(("System Manager", "Administrator"))
	return [p[0] for p in webnotes.conn.sql("""select distinct tabProfile.name 
		from tabUserRole, tabProfile where 
			tabUserRole.role=%s
			and tabProfile.name != "Administrator"
			and tabUserRole.parent = tabProfile.name
			and ifnull(tabProfile.enabled,0)=1""", role)]
