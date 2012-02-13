"""
Server side methods called from DocBrowser

Needs to be refactored
"""

import webnotes
from webnotes.utils import cint, cstr

sql = webnotes.conn.sql

@webnotes.whitelist()
def get_menu_items():
	"""
	   Returns a list of items to show in `Options` of the Web Notes Toolbar
	   List contains Pages and Single DocTypes
	"""
	import webnotes.utils

	rl = webnotes.user.get_roles() + [webnotes.session['user']]
	role_options = ["role = '"+r+"'" for r in rl]
	
	sql = webnotes.conn.sql
	menuitems = []
	
	# pages
	pages = sql("select distinct parent from `tabPage Role` where docstatus!=2 and (%s)" % (' OR '.join(role_options)))

	for p in pages:
		tmp = sql("select icon, parent_node, menu_index, show_in_menu from tabPage where name = '%s'" % p[0])
		if tmp and tmp[0][3]:
			menuitems.append(['Page', p[0] or '', tmp[0][1] or '', tmp[0][0] or '', webnotes.utils.cint(tmp[0][2])])
			
	# singles
	tmp = sql("select smallicon, parent_node, menu_index, name from tabDocType where (show_in_menu = 1 and show_in_menu is not null)")
	singles = {}
	for t in tmp: singles[t[3]] = t
		
	for p in webnotes.user.can_read:
		tmp = singles.get(p, None)
		if tmp: menuitems.append([p, p, tmp[1] or '', tmp[0] or '', int(tmp[2] or 0)])
		
	return menuitems
	
@webnotes.whitelist()
def has_result():
	"""return Yes if the given dt has any records"""
	return sql("select name from `tab%s` limit 1" % \
		webnotes.form_dict.get('dt')) and 'Yes' or 'No'

# --------------------------------------------------------------

def is_submittable(dt):
	return sql("select name from tabDocPerm where parent=%s and ifnull(submit,0)=1 and docstatus<1 limit 1", dt)

# --------------------------------------------------------------

def can_cancel(dt):
	return sql('select name from tabDocPerm where parent="%s" and ifnull(cancel,0)=1 and docstatus<1 and role in ("%s") limit 1' % (dt, '", "'.join(webnotes.user.get_roles())))

# --------------------------------------------------------------
def get_dt_trend(dt):
	ret = {}
	for r in sql("select datediff(now(),modified), count(*) from `tab%s` where datediff(now(),modified) between 0 and 30 group by date(modified)" % dt):
		ret[cint(r[0])] = cint(r[1])
	return ret

# --------------------------------------------------------------

def get_columns(out, sf, fl, dt, tag_fields):
	if not fl:
		fl = sf

	# subject
	subject = webnotes.conn.get_value('DocType', dt, 'subject')
	if subject:
		out['subject'] = subject
		
		# get fields from subject
		import re
		fl = re.findall('\%\( (?P<name> [^)]*) \)s', subject, re.VERBOSE)
		
		if tag_fields:
			fl += [t.strip() for t in tag_fields.split(',')]

	res = []
	for f in tuple(set(fl)):
		if f:
			res += [[c or '' for c in r] for r in sql("select fieldname, label, fieldtype, options from tabDocField where parent='%s' and fieldname='%s'" % (dt, f))]
			
	
	return res


# --------------------------------------------------------------
# NOTE: THIS SHOULD BE CACHED IN DOCTYPE CACHE
# --------------------------------------------------------------

@webnotes.whitelist()
def get_dt_details():
	"""
		Returns details called by DocBrowser this includes:
		the filters, columns, subject and tag_fields
		also if the doctype is of type "submittable"
	"""
	fl = eval(webnotes.form_dict.get('fl'))
	dt = webnotes.form_dict.get('dt')
	tag_fields, description = webnotes.conn.get_value('DocType', dt, ['tag_fields', 'description'])

	submittable = is_submittable(dt) and 1 or 0
 
	out = {
		'submittable':(is_submittable(dt) and 1 or 0), 
		'can_cancel':(can_cancel(dt) and 1 or 0)
	}

	# filters
	# -------

	sf = sql("select search_fields from tabDocType where name=%s", dt)[0][0] or ''

	# get fields from in_filter (if not in search_fields)
	if not sf.strip():
		res = sql("select fieldname, label, fieldtype, options from tabDocField where parent=%s and `in_filter` = 1 and ifnull(fieldname,'') != ''", dt)
		sf = [s[0] for s in res]
	else:
		sf = [s.strip() for s in sf.split(',')]
		res = sql("select fieldname, label, fieldtype, options from tabDocField where parent='%s' and fieldname in (%s)" % (dt, '"'+'","'.join(sf)+'"'))

	# select "link" options
	res = [[c or '' for c in r] for r in res]
	for r in res:
		if r[2]=='Select' and r[3] and r[3].startswith('link:'):
			tdt = r[3][5:]
			ol = sql("select name from `tab%s` where docstatus!=2 order by name asc" % tdt)
			r[3] = "\n".join([''] + [o[0] for o in ol])

	if not res:
		out['filters'] = [['name', 'ID', 'Data', '']]
	else:
		out['filters'] = [['name', 'ID', 'Data', '']] + res
	
	# columns
	# -------
	res = get_columns(out, sf, fl, dt, tag_fields)
	
	from webnotes.widgets.tags import check_user_tags
	check_user_tags(dt)
	
	out['columns'] = [['name', 'ID', 'Link', dt], ['modified', 'Modified', 'Data', ''], ['_user_tags', 'Tags', 'Data', '']] + res
	out['tag_fields'] = tag_fields
	out['description'] = description
	
	return out


@webnotes.whitelist()
def get_trend():
	return {'trend': get_dt_trend(webnotes.form_dict.get('dt'))}


@webnotes.whitelist()
def delete_items():
	"""delete selected items"""
	il = eval(webnotes.form_dict.get('items'))
	from webnotes.model import delete_doc
	from webnotes.model.code import get_obj
	
	for d in il:
		dt_obj = get_obj(d[0], d[1])
		if hasattr(dt_obj, 'on_trash'):
			dt_obj.on_trash()
		delete_doc(d[0], d[1])

@webnotes.whitelist()
def archive_items():
	"""archinve selected items"""
	il = eval(webnotes.form_dict.get('items'))
	
	from webnotes.utils.archive import archive_doc
	for d in il:
		archive_doc(d[0], d[1], webnotes.form_dict.get('action')=='Restore' and 1 or 0)
