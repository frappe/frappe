from pypika.terms import Term

import frappe


class Subquery(Term):
	def __init__(self, query):
		self.query = query

	def get_sql(self, **kwargs):
		return f"({self.query.get_sql(**kwargs)})"


# copy communication_date from Communication to Communication Link
def execute():
	cl = frappe.qb.DocType("Communication Link")
	c = frappe.qb.DocType("Communication")
	batch_size = 10_000

	while True:
		ids = (
			frappe.qb.from_(cl)
			.join(c)
			.on(cl.parent == c.name)
			.select(cl.name)
			.where(cl.communication_date.isnull())
			.where(c.communication_date.isnotnull())
			.limit(batch_size)
		).run(pluck=True)

		if not ids:
			break

		subquery = frappe.qb.from_(c).select(c.communication_date).where(c.name == cl.parent)

		(frappe.qb.update(cl).set(cl.communication_date, Subquery(subquery)).where(cl.name.isin(ids))).run()

		frappe.db.commit()
