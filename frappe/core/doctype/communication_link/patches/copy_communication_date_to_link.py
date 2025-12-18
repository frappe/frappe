import frappe


  # copy communication_date from Communication to Communication Link
  def execute():
      batch_size = 10_000

      while True:
          # Update communication_date in batches
          frappe.db.multisql(
              {
                  "postgres": """
                      UPDATE "tabCommunication Link" cl
                      SET communication_date = c.communication_date
                      FROM "tabCommunication" c
                      WHERE cl.parent = c.name
                      AND cl.communication_date IS NULL
                      AND c.communication_date IS NOT NULL
                      LIMIT %s
                  """,
                  "mariadb": """
                      UPDATE `tabCommunication Link` cl
                      INNER JOIN `tabCommunication` c ON cl.parent = c.name
                      SET cl.communication_date = c.communication_date
                      WHERE cl.communication_date IS NULL
                      AND c.communication_date IS NOT NULL
                      LIMIT %s
                  """,
              },
              values=(batch_size,),
          )

          frappe.db.commit()

          # Check if more rows need updating
          check = frappe.db.multisql(
              {
                  "postgres": """
                      SELECT 1 FROM "tabCommunication Link" cl
                      INNER JOIN "tabCommunication" c ON cl.parent = c.name
                      WHERE cl.communication_date IS NULL
                      AND c.communication_date IS NOT NULL
                      LIMIT 1
                  """,
                  "mariadb": """
                      SELECT 1 FROM `tabCommunication Link` cl
                      INNER JOIN `tabCommunication` c ON cl.parent = c.name
                      WHERE cl.communication_date IS NULL
                      AND c.communication_date IS NOT NULL
                      LIMIT 1
                  """,
              }
          )

          if not check:
              break
