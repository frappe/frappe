import frappe

def execute():
	frappe.reload_doctype("Communication")
	data = frappe.db.sql("""select dup.name as ref_name,comm.name as name,comm.message_id as message_id  from `tabCommunication` as comm
  		inner join ( select name,message_id
		from tabCommunication 
		where message_id is not null
		group by message_id having count(*) > 1) dup
    on comm.message_id = dup.message_id""",as_dict=1)
		
	for d in data:
		frappe.db.sql("""update tabCommunication
		set timeline_hide = %(ref_name)s
		where name = %(name)s """,{"name":d.name,"ref_name":d.ref_name
		                                    })
		
		frappe.db.sql("""update tabCommunication
				set timeline_hide = null
				where name = %(ref_name)s""", {"ref_name": d.ref_name})