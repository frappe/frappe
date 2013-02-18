from __future__ import unicode_literals
import webnotes
import memc

# User

def set_user_default(key, value, user=None):
	set_default(key, value, user or webnotes.session.user)

def add_user_default(key, value, user=None):
	add_default(key, value, user or webnotes.session.user)

def get_user_default(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	if d is None:
		d = get_global_default(key)
	return isinstance(d, list) and d[0] or d

def get_user_defaults(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	if d is None:
		d = get_global_defaults(key)
	return isinstance(d, basestring) and [d] or d
	
def get_all_user_defaults(user=None):
	userd = get_defaults(user or webnotes.session.user)
	globald = get_defaults()
	
	globald.update(userd)
	return globald

def clear_user_default(key, user=None):
	clear_default(key, user or webnotes.session.user)

# Global

def set_global_default(key, value):
	set_default(key, value, "Control Panel")

def add_global_default(key, value):
	add_default(key, value, "Control Panel")

def get_global_default(key):
	d = get_defaults().get(key, None)
	return isinstance(d, list) and d[0] or d
	
def get_global_defaults(key):
	d = get_defaults().get(key, None)
	return isinstance(d, basestring) and [d] or d
	
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
	
def clear_default(key, parent="Control Panel"):
	webnotes.conn.sql("""delete from tabDefaultValue where defkey=%s and parent=%s""", (key, parent))
	clear_cache(parent)
	
def get_defaults(parent="Control Panel"):
	"""get all defaults"""
	defaults = webnotes.cache().get_value("__defaults:" + parent)
	if not defaults:
		if parent=="Control Panel":
			res = webnotes.conn.sql("""select defkey, defvalue from `tabDefaultValue` 
				where parent = %s order by creation""", parent, as_dict=1)
		else:
			roles = webnotes.get_roles()
			res = webnotes.conn.sql("""select defkey, defvalue from `tabDefaultValue` 
				where parent in ('%s') order by creation""" % ("', '".join(roles)), as_dict=1)

		defaults = webnotes._dict({})
		for d in res:
			if d.defkey in defaults:
				# listify
				if isinstance(defaults[d.defkey], basestring):
					defaults[d.defkey] = [defaults[d.defkey]]
				defaults[d.defkey].append(d.defvalue)
			else:
				defaults[d.defkey] = d.defvalue

		webnotes.cache().set_value("__defaults:" + parent, defaults)
	
	return defaults

def clear_cache(parent):
	webnotes.cache().delete_value("__defaults:" + parent)
	webnotes.clear_cache()