# Modules
# -----------

def get_module_items(mod, only_dt=0):
	dl = []
	if only_dt:
		transfer_types = ['DocType']
	else:
		transfer_types = ['Role', 'Page', 'DocType', 'DocType Mapper', 'Search Criteria']
		dl = ['Module Def,'+mod]
	
	for dt in transfer_types:
		try:
			dl2 = sql('select name from `tab%s` where module="%s"' % (dt,mod))
			dl += [(dt+','+e[0]) for e in dl2]
		except:
			pass

	if not only_dt:
		dl1 = sql('select doctype_list from `tabModule Def` where name=%s', mod)
		dl += dl1[0][0].split('\n')
	
	# build finally
	dl = [e.split(',') for e in dl]
	dl = [[e[0].strip(), e[1].strip()] for e in dl] # remove blanks
	return dl