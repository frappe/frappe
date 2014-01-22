import webnotes

def execute():
	webnotes.reload_doc("core", "doctype", "docperm")
	
	# delete same as cancel (map old permissions)
	webnotes.conn.sql("""update tabDocPerm set `delete`=ifnull(`cancel`,0)""")
	
	# can't cancel if can't submit
	webnotes.conn.sql("""update tabDocPerm set `cancel`=0 where ifnull(`submit`,0)=0""")
	
	webnotes.clear_cache()