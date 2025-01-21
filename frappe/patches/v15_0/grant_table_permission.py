import frappe


def execute():
    db_name = frappe.conf.db_name
    
    sql_commands = [
        f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_name};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {db_name};"
    ]
    
    for sql_cmd in sql_commands:
        frappe.db.sql(sql_cmd)
        frappe.db.commit()
    print("Database permissions updated successfully")