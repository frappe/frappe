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
	return isinstance(d, list) and d[0] or d

def get_user_default_as_list(key, user=None):
	d = get_defaults(user or webnotes.session.user).get(key, None)
	return isinstance(d, basestring) and [d] or d
	
def get_defaults(user=None):
	userd = get_defaults_for(user or webnotes.session.user)
	
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
				if isinstance(defaults[d.defkey], basestring) and defaults[d.defkey] != d.defvalue:
					defaults[d.defkey] = [defaults[d.defkey]]
				if d.defvalue not in defaults[d.defkey]:
					defaults[d.defkey].append(d.defvalue)
			else:
				defaults[d.defkey] = d.defvalue

		webnotes.cache().set_value("__defaults:" + parent, defaults)
	
	return defaults

def clear_cache(parent=None):
	def all_profiles():
		return webnotes.conn.sql_list("select name from tabProfile") + ["Control Panel"]
		
	if parent=="Control Panel" or not parent:
		parent = all_profiles()
	elif isinstance(parent, basestring):
		parent = [parent]
		
	for p in parent:
		webnotes.cache().delete_value("__defaults:" + p)

	webnotes.clear_cache()