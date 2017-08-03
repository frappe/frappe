# Tareas Programadas

Finalmente, una aplicación también tiene que mandar notificaciones de email y hacer otros tipos de tareas programadas. En Frappé, si tienes el bench configurado, el programador de tareas es configurado vía Celery usando Redis Queue.

Para agregar un nuevo manejador(Handler) de tareas, ir a `hooks.py` y agrega un nuevo manejador. Los manejadores (Handlers) por defecto son `all`, `daily`, `weekly`, `monthly`. El manejador `all` es llamado cada 3 minutos por defecto.

	# Tareas Programadas
	# ---------------

	scheduler_events = {
		"daily": [
			"library_management.tasks.daily"
		],
	}

Aquí hacemos referencia a una función Python que va a ser ejecutada diariamente. Vamos a ver como se ve esta función:

	# Copyright (c) 2013, Frappé
	# For license information, please see license.txt

	from __future__ import unicode_literals
	import frappe
	from frappe.utils import datediff, nowdate, format_date, add_days

	def daily():
		loan_period = frappe.db.get_value("Library Management Settings",
			None, "loan_period")

		overdue = get_overdue(loan_period)

		for member, items in overdue.iteritems():
			content = """<h2>Following Items are Overdue</h2>
			<p>Please return them as soon as possible</p><ol>"""

			for i in items:
				content += "<li>{0} ({1}) due on {2}</li>".format(i.article_name,
					i.article,
					format_date(add_days(i.transaction_date, loan_period)))

			content += "</ol>"

			recipient = frappe.db.get_value("Library Member", member, "email_id")
			frappe.sendmail(recipients=[recipient],
				sender="test@example.com",
				subject="Library Articles Overdue", content=content, bulk=True)

	def get_overdue(loan_period):
		# check for overdue articles
		today = nowdate()

		overdue_by_member = {}
		articles_transacted = []

		for d in frappe.db.sql("""select name, article, article_name,
			library_member, member_name
			from `tabLibrary Transaction`
			order by transaction_date desc, modified desc""", as_dict=1):

			if d.article in articles_transacted:
				continue

			if d.transaction_type=="Issue" and \
				datediff(today, d.transaction_date) > loan_period:
				overdue_by_member.setdefault(d.library_member, [])
				overdue_by_member[d.library_member].append(d)

			articles_transacted.append(d.article)

Podemos pegar el código anterior en cualquier módulo de Python que sea accesible. La ruta es definida en `hooks.py`, por lo que para nuestro propósito vamos a poner el código en el archivo `library_management/tasks.py`.

Nota:

1. Obtenemos el período de prestamo desde **Library Management Settings** usando la función `frappe.db.get_value`.
1. Ejecutamos una consulta en la base de datos usando la función `frappe.db.sql`
1. Los Email son enviados usando `frappe.sendmail`

{next}
