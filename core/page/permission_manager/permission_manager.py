from __future__ import unicode_literals
import webnotes

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_roles_and_doctypes():
	return {
		"doctypes": [d[0] for d in webnotes.conn.sql("""select name from tabDocType where
			ifnull(istable,0)=0 and
			ifnull(issingle,0)=0 and
			module != 'Core' """)],
		"roles": [d[0] for d in webnotes.conn.sql("""select name from tabRole where name not in
			('All', 'Guest', 'Administrator')""")]
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
	webnotes.conn.sql("""delete from tabDocPerm where name=%s""", name)
	validate_and_reset(doctype, for_remove=True)

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
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def update_match(name, doctype, match=""):
	webnotes.conn.sql("""update tabDocPerm set `match`=%s where name=%s""",
		(match, name))
	validate_and_reset(doctype)
	
def validate_and_reset(doctype, for_remove=False):
	from core.doctype.doctype.doctype import validate_permissions_for_doctype
	validate_permissions_for_doctype(doctype, for_remove)
	webnotes.clear_cache(doctype=doctype)
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def reset(doctype):
	webnotes.reset_perms(doctype)
	webnotes.clear_cache(doctype=doctype)

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_users_with_role(role):
	return [p[0] for p in webnotes.conn.sql("""select distinct tabProfile.name 
		from tabUserRole, tabProfile where 
			tabUserRole.role=%s
			and tabProfile.name != "Administrator"
			and tabUserRole.parent = tabProfile.name
			and ifnull(tabProfile.enabled,0)=1""", role)]
