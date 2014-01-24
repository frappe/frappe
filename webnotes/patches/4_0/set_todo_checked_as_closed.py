import webnotes

def execute():
	webnotes.reload_doc("core", "doctype", "todo")
	webnotes.conn.sql("""update tabToDo set status = if(ifnull(checked,0)=0, 'Open', 'Closed')""")
