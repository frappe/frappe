import frappe
from frappe.tests.microbenchmarks.utils import NanoBenchmark

bench_qb_select_star = NanoBenchmark(
	'frappe.qb.from_(table).select("*").limit(20).run(run=0)',
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_select_star = NanoBenchmark(
	'frappe.qb.from_(table).select("*").limit(20).get_sql()',
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_select_multiple_fields = NanoBenchmark(
	"frappe.qb.from_(table).select(table.name, table.creation, table.modified).limit(20).run(run=0)",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_select_multiple_fields = NanoBenchmark(
	"frappe.qb.from_(table).select(table.name, table.creation, table.modified).limit(20).get_sql()",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_select_offset = NanoBenchmark(
	"frappe.qb.from_(table).select(table.name).limit(20).offset(10).get_sql()",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_select_distinct = NanoBenchmark(
	"frappe.qb.from_(table).select(table.name).distinct().limit(20).get_sql()",
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


bench_qb_render_join_filters = NanoBenchmark(
	"""(
	frappe.qb.from_(user)
	.join(has_role)
	.on(has_role.parent == user.name)
	.select(user.name, user.email, has_role.role)
	.where((user.enabled == 1) & (has_role.role.isin(roles)) & user.email.like("%@example.com"))
	.orderby(user.creation)
	.limit(20)
	.get_sql()
)""",
	setup="""user = frappe.qb.DocType("User")
has_role = frappe.qb.DocType("Has Role")
roles = ["System Manager", "Administrator", "Guest"]""",
)


bench_qb_render_insert = NanoBenchmark(
	"""(
	frappe.qb.into(table)
	.columns("doctype", "field", "value")
	.insert("User", "language", "en")
	.get_sql()
)""",
	setup='table = frappe.qb.DocType("Singles")',
)


bench_qb_walk_insert = NanoBenchmark(
	"""(
	frappe.qb.into(table)
	.columns("doctype", "field", "value")
	.insert("User", "language", "en")
	.walk()
)""",
	setup='table = frappe.qb.DocType("Singles")',
)


bench_qb_render_update = NanoBenchmark(
	"""(
	frappe.qb.update(table)
	.set(table.disabled, 0)
	.where((table.name == "Guest") & (table.modified >= "2020-01-01 00:00:00"))
	.get_sql()
)""",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_walk_update_no_where = NanoBenchmark(
	"""(
	frappe.qb.update(table)
	.set(table.disabled, 0)
	.walk()
)""",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_delete = NanoBenchmark(
	"""(
	frappe.qb.from_(table)
	.delete()
	.where((table.name == "Not_GUEST") | table.modified.isnull())
	.get_sql()
)""",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_walk_delete_no_where = NanoBenchmark(
	"""(
	frappe.qb.from_(table)
	.delete()
	.walk()
)""",
	setup='table = frappe.qb.DocType("Role")',
)


bench_qb_render_functions = NanoBenchmark(
	"""(
	frappe.qb.from_(table)
	.select(Count(table.name), Coalesce(table.disabled, 0), Max(table.modified))
	.where(table.name.isin(roles))
	.groupby(table.disabled)
	.get_sql()
)""",
	setup="""from frappe.query_builder.functions import Coalesce, Count, Max
table = frappe.qb.DocType("Role")
roles = ["Guest", "Administrator", "System Manager"]""",
)


bench_qb_render_grouped_count_alias_order = NanoBenchmark(
	"""(
	frappe.qb.from_(table)
	.select(table.fieldtype, Count(table.name).as_("field_count"))
	.groupby(table.fieldtype)
	.orderby(Field("field_count"), order=frappe.qb.desc)
	.limit(20)
	.get_sql()
)""",
	setup="""from pypika.terms import Field
from frappe.query_builder.functions import Count
table = frappe.qb.DocType("DocField")""",
)


bench_qb_walk_parameterized = NanoBenchmark(
	"""(
	frappe.qb.from_(table)
	.select(table.name)
	.where((table.name == "Administrator' --") & table.modified.notnull())
	.walk()
)""",
	setup='table = frappe.qb.DocType("User")',
)


bench_qb_complex_report = NanoBenchmark(
	"""query = (
		frappe.qb.from_(sle)
		.select(
			sle.item_code,
			sle.posting_datetime.as_("date"),
			sle.warehouse,
			sle.posting_date,
			sle.posting_time,
			sle.actual_qty,
			sle.incoming_rate,
			sle.valuation_rate,
			sle.company,
			sle.voucher_type,
			sle.qty_after_transaction,
			sle.stock_value_difference,
			sle.serial_and_batch_bundle,
			sle.voucher_no,
			sle.stock_value,
			sle.batch_no,
			sle.serial_no,
			sle.project,
		)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
			& (sle.posting_datetime[from_date:to_date])
		)
		.orderby(sle.posting_datetime)
		.orderby(sle.creation)
	)

for fieldname in inventory_dimension_fields:
	query = query.select(sle[fieldname])
	if filters.get(fieldname):
		query = query.where(sle[fieldname].isin(filters[fieldname]))

if items:
	query = query.where(sle.item_code.isin(items))

for field in ("voucher_no", "project", "company"):
	if filters.get(field) and field not in inventory_dimension_fields:
		query = query.where(sle[field] == filters[field])

if filters.get("batch_no"):
	if bundles:
		query = query.where(
			(sle.serial_and_batch_bundle.isin(bundles)) | (sle.batch_no == filters["batch_no"])
		)
	else:
		query = query.where(sle.batch_no == filters["batch_no"])

if filters.get("warehouse"):
	child_query = frappe.qb.from_(warehouse).select(warehouse.name)
	range_conditions = [
		(warehouse.lft >= lft) & (warehouse.rgt <= rgt) for lft, rgt in warehouse_ranges
	]
	combined_condition = range_conditions[0]
	for condition in range_conditions[1:]:
		combined_condition = combined_condition | condition

	child_query = child_query.where(combined_condition).where(warehouse.name == sle.warehouse)
	query = query.where(ExistsCriterion(child_query))

query.run(run=0)""",
	setup="""from pypika.terms import ExistsCriterion

sle = frappe.qb.DocType("Stock Ledger Entry")
warehouse = frappe.qb.DocType("Warehouse")
from_date = "2024-01-01 00:00:00"
to_date = "2024-12-31 23:59:59"
items = [f"ITEM-{idx:05d}" for idx in range(100)]
bundles = [f"SABB-{idx:05d}" for idx in range(25)]
warehouse_ranges = [(1, 500), (1001, 1500), (2001, 2500)]
inventory_dimension_fields = ["inventory_dimension_1", "inventory_dimension_2", "inventory_dimension_3"]
filters = {
	"warehouse": ["Stores - ACME", "Finished Goods - ACME", "Work In Progress - ACME"],
	"voucher_no": "MAT-STE-2024-00001",
	"project": "PROJ-0001",
	"company": "ACME Manufacturing",
	"batch_no": "BATCH-2024-0001",
	"inventory_dimension_1": ["Plant A", "Plant B", "Plant C"],
	"inventory_dimension_2": ["Retail", "Wholesale"],
	"inventory_dimension_3": ["North", "South", "West"],
}""",
)
