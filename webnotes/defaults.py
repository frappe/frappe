# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def set_user_default(key, value, user=None):
	set_default(key, value, user or webnotes.session.user)

def add_user_default(key, value, user=None):
	add_default(key, value, user or webnotes.session.user)

def get_user_default(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	return isinstance(d, list) and d[0] or d

def get_user_default_as_list(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	return (not isinstance(d, list)) and [d] or d
	
def get_defaults(user=None):
	if not user:
		user = webnotes.session.user if webnotes.session else "Guest"

	userd = get_defaults_for(user)
	userd.update({"user": user, "owner": user})
	
	globald = get_defaults_for()
	globald.update(userd)
	
	return globald

def clear_user_default(key, user=None):
	clear_default(key, parent=user or webnotes.session.user)

# Global

def set_global_default(key, value):
	set_default(key, value, "Control Panel")

def add_global_default(key, value):
	add_default(key, value, "Control Panel")

def get_global_default(key):
	d = get_defaults().get(key, None)
	return isinstance(d, list) and d[0] or d
	
# Common

def set_default(key, value, parent):
	if webnotes.conn.sql("""select defkey from `tabDefaultValue` where 
		defkey=%s and parent=%s """, (key, parent)):
		# update
		webnotes.conn.sql("""update `tabDefaultValue` set defvalue=%s 
			where parent=%s and defkey=%s""", (value, parent, key))
		clear_cache(parent)
	else:
		add_default(key, value, parent)

def add_default(key, value, parent):
	d = webnotes.doc({
		"doctype": "DefaultValue",
		"parent": parent,
		"parenttype": "Control Panel",
		"parentfield": "system_defaults",
		"defkey": key,
		"defvalue": value
	})
	d.insert()
	clear_cache(parent)
	
def clear_default(key=None, value=None, parent=None, name=None):
	conditions = []
	values = []

	if key:
		conditions.append("defkey=%s")
		values.append(key)
	
	if value:
		conditions.append("defvalue=%s")
		values.append(value)
		
	if name:
		conditions.append("name=%s")
		values.append(name)
		
	if parent:
		conditions.append("parent=%s")
		values.append(parent)
	
	if not conditions:
		raise Exception, "[clear_default] No key specified."
	
	webnotes.conn.sql("""delete from tabDefaultValue where %s""" % " and ".join(conditions), values)
	clear_cache()
	
def get_defaults_for(parent="Control Panel"):
	"""get all defaults"""
	defaults = webnotes.cache().get_value("__defaults:" + parent)
	if not defaults:
		res = webnotes.conn.sql("""select defkey, defvalue from `tabDefaultValue` 
			where parent = %s order by creation""", parent, as_dict=1)

		defaults = webnotes._dict({})
		for d in res:
			if d.defkey in defaults:
				# listify
				if not isinstance(defaults[d.defkey], list) and defaults[d.defkey] != d.defvalue:
					defaults[d.defkey] = [defaults[d.defkey]]
				
				if d.defvalue not in defaults[d.defkey]:
					defaults[d.defkey].append(d.defvalue)
			elif d.defvalue is not None:
				defaults[d.defkey] = d.defvalue
		
		if webnotes.session and parent == webnotes.session.user:
			defaults.update(get_defaults_for_match(defaults))

		webnotes.cache().set_value("__defaults:" + parent, defaults)
	
	return defaults

def get_defaults_for_match(userd):
	"""	if a profile based match condition exists for a user's role 
		and no user property is specified for that match key,
		set default value as user's profile for that match key"""
	user_roles = webnotes.get_roles()
	out = {}
	
	for role, match in webnotes.conn.sql("""select distinct role, `match`
		from `tabDocPerm` where ifnull(permlevel, 0)=0 and `read`=1 
		and `match` like "%:user" """):
			if role in user_roles and match.split(":")[0] not in userd:
				out[match.split(":")[0]] = webnotes.session.user

	return out

def clear_cache(parent=None):
	def all_profiles():
		return webnotes.conn.sql_list("select name from tabProfile") + ["Control Panel", "__global"]
		
	if parent=="Control Panel" or not parent:
		parent = all_profiles()
	elif isinstance(parent, basestring):
		parent = [parent]
		
	for p in parent:
		webnotes.cache().delete_value("__defaults:" + p)

	webnotes.clear_cache()