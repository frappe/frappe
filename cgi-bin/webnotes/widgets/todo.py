# ToDO and Reminder
# -----------------

def add_todo(user, date, priority, desc, ref_type, ref_name):
	nlist = []
	if type(user)==list:
		for i in user:
			nlist.append(add_todo_item(i, date, priority, desc, ref_type, ref_name))
		return nlist
	else:
		return add_todo_item(user, date, priority, desc, ref_type, ref_name)	
	
def add_todo_item(user, date, priority, desc, ref_type, ref_name):
	if not date:
		date = nowdate()

	d = Document('ToDo Item')
	d.owner = user
	d.date = date
	d.priority = priority
	d.description = desc
	d.reference_type = ref_type
	d.reference_name = ref_name
	d.save(1)
	return d.name
	
def remove_todo(name):
	if type(name)==list:
		for i in name:
			sql("delete from `tabToDo Item` where name='%s'" % i)
	else:
		sql("delete from `tabToDo Item` where name='%s'" % name)

def get_todo_list():
	c = getcursor()
	try:
		role_options = ["role = '"+r+"'" for r in roles]
		role_options = role_options and ' OR ' + ' OR '.join(role_options) or ''
		c.execute("select * from `tabToDo Item` where owner='%s' %s" % (session['user'], role_options))
	except: # deprecated
		c.execute("select * from `tabToDo Item` where owner='%s'" % session['user'])
	dataset = c.fetchall()
	l = []
	for i in range(len(dataset)):
		d = Document('ToDo Item')
		d.loadfields(dataset, i, c.description)
		l.append(d)
		
	return l