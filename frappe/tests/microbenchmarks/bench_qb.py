import frappe
from frappe.tests.microbenchmarks.utils import NanoBenchmark

bench_qb_select_star = NanoBenchmark(
	'frappe.qb.from_(table).select("*").limit(20).run(run=0)',
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_select_multiple_fields = NanoBenchmark(
	"frappe.qb.from_(table).select(table.name, table.creation, table.modified).limit(20).run(run=0)",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_get_query = NanoBenchmark(
	"""frappe.qb.get_query(
		"Role",
		filters={"creation": (">", "2020-01-01 00:00:00")},
		fields="disabled",
		limit=10,
		order_by="creation asc",
	).run(run=0)"""
)

bench_qb_get_query_multiple_fields = NanoBenchmark(
	"""frappe.qb.get_query(
		"Role",
		filters={"creation": (">", "2020-01-01 00:00:00")},
		fields=["disabled", "name", "creation", "modified"],
		limit=10,
		order_by="creation asc",
	).run(run=0)"""
)


bench_qb_simple_get_query = NanoBenchmark(
	"""frappe.qb.get_query(
									"Role",
									filters={"name": "Guest"},
									fields="*",
									limit=1,
									order_by="creation asc",
								).run(run=0)"""
)
