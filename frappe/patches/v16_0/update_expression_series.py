import frappe
from frappe.model.naming import (
	BRACED_PARAMS_WORD_PATTERN,
	NAMING_SERIES_PART_TYPES,
	determine_consecutive_week_number,
	has_custom_parser,
)
from frappe.query_builder import DocType
from frappe.utils import cstr


def execute():
	Series = DocType("Series")
	doctypes = frappe.get_all("DocType", filters={"naming_rule": "expression"}, fields=["name", "autoname"])
	uniq_exprs = set()

	def get_param_value_for_word_match(doc):
		def get_param_value(match):
			e = match.group()[1:-1]
			creation = doc.creation
			_sentinel = object()
			part = ""
			if e == "YY":
				part = creation.strftime("%y")
			elif e == "MM":
				part = creation.strftime("%m")
			elif e == "DD":
				part = creation.strftime("%d")
			elif e == "YYYY":
				part = creation.strftime("%Y")
			elif e == "WW":
				part = determine_consecutive_week_number(creation)
			elif e == "timestamp":
				part = str(creation)
			elif doc and (e.startswith("{") or doc.get(e, _sentinel) is not _sentinel):
				e = e.replace("{", "").replace("}", "")
				part = doc.get(e)
			elif method := has_custom_parser(e):
				part = frappe.get_attr(method[0])(doc, e)
			else:
				part = e

			if isinstance(part, NAMING_SERIES_PART_TYPES):
				part = cstr(part).strip()

			return part

		return get_param_value

	for doctype in doctypes:
		if "#" in doctype.autoname:
			docs = frappe.get_all(doctype.name)
			if docs:
				for doc in docs:
					_doc = frappe.get_doc(doctype.name, doc.name)
					expr = doctype.autoname[7 : doctype.autoname.find("{#")]
					key = BRACED_PARAMS_WORD_PATTERN.sub(get_param_value_for_word_match(_doc), expr)
					uniq_exprs.add(key)

	current = (frappe.qb.from_(Series).select("*").where(Series.name == "")).run(as_dict=True)
	if current:
		current = current[0].get("current")

		for uniq_expr in uniq_exprs:
			expr_exists = (frappe.qb.from_(Series).select("*").where(Series.name == uniq_expr)).run(
				as_dict=True
			)
			if not expr_exists:
				(frappe.qb.into(Series).columns("name", "current").insert(uniq_expr, current + 1)).run()
