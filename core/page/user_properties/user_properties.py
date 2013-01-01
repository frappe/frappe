from __future__ import unicode_literals
import webnotes

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_users_and_links():
	links = list(set(webnotes.conn.sql("""select fieldname, options
		from tabDocField where fieldtype='Link' 
		and parent not in ('[Select]', 'DocType', 'Module Def')
		""") + webnotes.conn.sql("""select fieldname, options
		from `tabCustom Field` where fieldtype='Link'""")))
	links.sort()

	return {
		"users": [d[0] for d in webnotes.conn.sql("""select name from tabProfile where
			ifnull(enabled,0)=1 and
			name not in ("Administrator", "Guest")""")],
		"link_fields": links
	}
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_properties(user=None, key=None):
	return webnotes.conn.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where %s%s and parent!='Control Panel' order by parent, defkey""" % (\
			user and (" parent='%s'" % user) or "",
			key and ((user and " and " or "") + " defkey='%s'" % key) or "",
			), as_dict=True)

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def remove(user, name):
	webnotes.conn.sql("""delete from tabDefaultValue where name=%s""", name)
	webnotes.clear_cache(user=user)
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def add(parent, defkey, defvalue):
	webnotes.conn.add_default(defkey, defvalue, parent)
