# Scheduled Tasks

Finally, an application also has to send email notifications and do other kind of scheduled tasks. In Frappe, if you have setup the bench, the task / scheduler is setup via Celery using Redis Queue.

To add a new task handler, go to `hooks.py` and add a new handler. Default handlers are `all`, `daily`, `weekly`, `monthly`. The `all` handler is called every 3 minutes by default.

	# Scheduled Tasks
	# ---------------

	scheduler_events = {
		"daily": [
			"library_management.tasks.daily"
		],
	}

Here we can point to a Python function and that function will be executed every day. Let us look what this function looks like:

	# Copyright (c) 2013, Frappe
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

We can place the above code code in any accessible Python module. The route is defined in `hooks.py`, so for our purposes we would place this code in `library_management/tasks.py`.

Note:

1. We get the loan period from **Library Management Settings** by using `frappe.db.get_value`.
1. We run a query in the database with `frappe.db.sql`
1. Email is sent via `frappe.sendmail`

{next}
