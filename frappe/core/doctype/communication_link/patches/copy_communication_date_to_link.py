import frappe


  # copy communication_date from Communication to Communication Link
  def execute():
      batch_size = 10_000

      # Check if using PostgreSQL
      is_postgres = frappe.db.db_type == "postgres"

      while True:
          if is_postgres:
              # PostgreSQL syntax
              frappe.db.sql(
                  """
                  update "tabCommunication Link" cl
                  set communication_date = c.communication_date
                  from "tabCommunication" c
                  where cl.parent = c.name
                  and cl.communication_date is null
                  and c.communication_date is not null
                  limit %s
                  """,
                  (batch_size,),
              )
          else:
              # MySQL/MariaDB syntax
              frappe.db.sql(
                  """
                  update `tabCommunication Link` cl
                  inner join `tabCommunication` c on cl.parent = c.name
                  set cl.communication_date = c.communication_date
                  where cl.communication_date is null
                  and c.communication_date is not null
                  limit %s
                  """,
                  (batch_size,),
              )

          frappe.db.commit()

          # Check if more rows need updating
          if is_postgres:
              check = frappe.db.sql(
                  """
                  select 1 from "tabCommunication Link" cl
                  inner join "tabCommunication" c on cl.parent = c.name
                  where cl.communication_date is null
                  and c.communication_date is not null
                  limit 1
                  """
              )
          else:
              check = frappe.db.sql(
                  """
                  select 1 from `tabCommunication Link` cl
                  inner join `tabCommunication` c on cl.parent = c.name
                  where cl.communication_date is null
                  and c.communication_date is not null
                  limit 1
                  """
              )

          if not check:
              break
