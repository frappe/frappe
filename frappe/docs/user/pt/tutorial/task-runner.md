# Tarefas agendadas

Finalmente, uma aplicação também tem que enviar notificações de e-mail e fazer outros tipos de tarefas agendadas. Em Frappé, se você instalou o bench, o task / scheduler foi instalado via Celery usando Redis Queue.

Para adicionar um novo task handler, vá para `hooks.py` e adicione um novo handler. Handlers padrão são os `all`,` daily`, `weekly`,` monthly`. O handler `all` é chamado a cada 3 minutos por padrão.

	# Scheduled Tasks
	# ---------------

	scheduler_events = {
		"daily": [
			"library_management.tasks.daily"
		],
	}

Aqui podemos apontar para uma função Python e esta função será executada todos os dias. Vejamos como é essa função:

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

Nós podemos colocar o código acima em qualquer módulo Python acessível. A rota é definida em `hooks.py`, portanto, para os nossos propósitos, iremos colocar esse código em `library_management/tasks.py`.

Observação:

1. Nós pegamos o loan period de **Library Management Settings** usando `frappe.db.get_value`.
1. Nós rodamos uma query no banco de dados com `frappe.db.sql`
1. O email foi enviado via `frappe.sendmail`

{next}
