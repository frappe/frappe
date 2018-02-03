# Les tâches planifiées

Finalement, une application a aussi à envoyer des emails de notifications ou d'autres taches planifiées. Dans Frappé, si 
 vous avez configuré le **bench**, la tâche / planificateur est configuré via Celery en utilisant les queues Redis.

Pour ajouter un nouveau gestionnaire de tâches, ouvrez le fichier `hooks.py` et ajoutez un nouveau gestionnaire. Les gestionnaires
 par defaut sont `all`, `daily`, `weekly`, `monthly`. Le gestionanire `all` est appelé toutes les 3 minutes par defaut.

	# Scheduled Tasks
	# ---------------

	scheduler_events = {
		"daily": [
			"library_management.tasks.daily"
		],
	}

Ici, nous pointons sur une fonction en Python et cette fonction sera appelée tous les jours. Voyons à quoi cette fonction 
ressemble:

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

Nous pouvons placer ce code dans un n'importe quel module Python accessible. La route est définie dans `hooks.py`, dans cet exemple nos placerons ce code dans `library_management/tasks.py`.

Note:

1. Nous obtenons la durée de prêt depuis **Library Management Settings** en utilisant `frappe.db.get_value`.
1. Nous lancons une requête dans la base de données via `frappe.db.sql`
1. Les emails sont envoyés via `frappe.sendmail`

{suite}
