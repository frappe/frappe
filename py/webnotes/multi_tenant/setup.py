import webnotes

# setup all tables for multi-tenant
# ---------------------------------
def setup_tables():
	import webnotes.multi_tenant
	
	tl = webnotes.conn.sql("show tables")
	for t in tl:
		add_tenant_id(t[0])
		change_primary_key(t[0])

def add_tenant_id(tname):
	webnotes.conn.sql("alter table `%s` add column _tenant_id int(10) default 0 not null")
		
def change_primary_key(tname):
	webnotes.conn.sql("alter table `%s` drop primary key name")
	webnotes.conn.sql("alter table `%s` add primary key (name, _tenant_id)")
		
