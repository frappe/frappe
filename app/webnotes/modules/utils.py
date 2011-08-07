def listfolders(path, only_name=0):
	"""
		Returns the list of folders (with paths) in the given path, 
		If only_name is set, it returns only the folder names
	"""

	import os
	out = []
	for each in os.listdir(path):
		dirname = each.split(os.path.sep)[-1]
		fullpath = os.path.join(path, dirname)

		if os.path.isdir(fullpath) and not dirname.startswith('.'):
			out.append(only_name and dirname or fullname)
	return out

def switch_module(dt, dn, to, frm=None, export=None):
	"""
		Change the module of the given doctype, if export is true, then also export txt and copy
		code files from src
	"""
	import os
	webnotes.conn.sql("update `tab"+dt+"` set module=%s where name=%s", (to, dn))

	if export:
		export_doc(dt, dn)

		# copy code files
		if dt in ('DocType', 'Page', 'Search Criteria'):
			from_path = os.path.join(get_module_path(frm), scrub(dt), scrub(dn), scrub(dn))
			to_path = os.path.join(get_module_path(to), scrub(dt), scrub(dn), scrub(dn))

			# make dire if exists
			os.system('mkdir -p %s' % os.path.join(get_module_path(to), scrub(dt), scrub(dn)))

			for ext in ('py','js','html','css'):
				os.system('cp %s %s')
