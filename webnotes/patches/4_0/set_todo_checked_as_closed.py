import webnotes

def execute():
	webnotes.conn.sql("""update tabToDo set status = if(ifnull(checked,0)=0, 'Open', 'Closed')""")
