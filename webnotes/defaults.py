# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import memc

# User

def set_user_default(key, value, user=None, parenttype=None):
	set_default(key, value, user or webnotes.session.user, parenttype)

def add_user_default(key, value, user=None, parenttype=None):
	add_default(key, value, user or webnotes.session.user, parenttype)

def get_user_default(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	return isinstance(d, list) and d[0] or d

def get_user_default_as_list(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	return (not isinstance(d, list)) and [d] or d

def get_restrictions():
	if webnotes.local.restrictions is None:
		out = {}
		for key, value in webnotes.conn.sql("""select defkey, defvalue 
			from tabDefaultValue where parent=%s and parenttype='Restriction'""", webnotes.session.user):
			out.setdefault(key, [])
			out[key].append(value)
			
		webnotes.local.restrictions = out
	return webnotes.local.restrictions

def get_defaults(user=None):
	if not user and webnotes.session:
		user = webnotes.session.user

	if user:
		userd = get_defaults_for(user)
		
		if user in ["__global", "Control Panel"]:
			userd.update({"user": webnotes.session.user, "owner": webnotes.session.user})
		else:
			userd.update({"user": user, "owner": user})
	else:
		userd = {}
	
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

def set_default(key, value, parent, parenttype="Control Panel"):
	if webnotes.conn.sql("""select defkey from `tabDefaultValue` where 
		defkey=%s and parent=%s """, (key, parent)):
		# update
		webnotes.conn.sql("""update `tabDefaultValue` set defvalue=%s, parenttype=%s 
			where parent=%s and defkey=%s""", (value, parenttype, parent, key))
		clear_cache(parent)
	else:
		add_default(key, value, parent)

def add_default(key, value, parent, parenttype=None):
	d = webnotes.doc({
		"doctype": "DefaultValue",
		"parent": parent,
		"parenttype": parenttype or "Control Panel",
		"parentfield": "system_defaults",
		"defkey": key,
		"defvalue": value
	})
	d.insert()
	if parenttype=="Restriction":
		webnotes.local.restrictions = None
	clear_cache(parent)
	
def clear_default(key=None, value=None, parent=None, name=None, parenttype=None):
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
		clear_cache(parent)
		values.append(parent)
	else:
		clear_cache("Control Panel")
		clear_cache("__global")
		
	if parenttype:
		conditions.append("parenttype=%s")
		values.append(parenttype)
		if parenttype=="Restriction":
			webnotes.local.restrictions = None
	
	if not conditions:
		raise Exception, "[clear_default] No key specified."
	
	webnotes.conn.sql("""delete from tabDefaultValue where %s""" % " and ".join(conditions), values)
	webnotes.clear_cache(sessions_only=True)
	
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
		
		webnotes.cache().set_value("__defaults:" + parent, defaults)
	
	return defaults

def clear_cache(parent=None):
	if webnotes.flags.in_install: 
		return

	def all_profiles():
		return webnotes.conn.sql_list("select name from tabProfile") + ["Control Panel", "__global"]
		
	if parent=="Control Panel" or not parent:
		parent = all_profiles()
	elif isinstance(parent, basestring):
		parent = [parent]
		
	for p in parent:
		webnotes.cache().delete_value("__defaults:" + p)

	webnotes.clear_cache(sessions_only=True)
