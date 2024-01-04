# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.boot import get_allowed_report_names
from frappe.config import get_modules_from_all_apps_for_user
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.modules.export_file import export_to_files
from frappe.query_builder import Criterion
from frappe.query_builder.utils import DocType
from frappe.utils import cint, flt


class NumberCard(Document):
	def autoname(self):
		if not self.name:
			self.name = self.label

		if frappe.db.exists("Number Card", self.name):
			self.name = append_number_if_name_exists("Number Card", self.name)

	def validate(self):
		if self.type == "Document Type":
			if not (self.document_type and self.function):
				frappe.throw(_("Document Type and Function are required to create a number card"))

			if self.function != "Count" and not self.aggregate_function_based_on:
				frappe.throw(_("Aggregate Field is required to create a number card"))

			if frappe.get_meta(self.document_type).istable and not self.parent_document_type:
				frappe.throw(_("Parent Document Type is required to create a number card"))

		elif self.type == "Report":
			if not (self.report_name and self.report_field and self.function):
				frappe.throw(_("Report Name, Report Field and Fucntion are required to create a number card"))

		elif self.type == "Custom":
			if not self.method:
				frappe.throw(_("Method is required to create a number card"))

	def on_update(self):
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[["Number Card", self.name]], record_module=self.module)


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return None

	doctype_condition = False
	module_condition = False

	allowed_doctypes = [
		frappe.db.escape(doctype) for doctype in frappe.permissions.get_doctypes_with_read()
	]
	allowed_modules = [
		frappe.db.escape(module.get("module_name")) for module in get_modules_from_all_apps_for_user()
	]

	if allowed_doctypes:
		doctype_condition = "`tabNumber Card`.`document_type` in ({allowed_doctypes})".format(
			allowed_doctypes=",".join(allowed_doctypes)
		)
	if allowed_modules:
		module_condition = """`tabNumber Card`.`module` in ({allowed_modules})
			or `tabNumber Card`.`module` is NULL""".format(
			allowed_modules=",".join(allowed_modules)
		)

	return """
		{doctype_condition}
		and
		{module_condition}
	""".format(
		doctype_condition=doctype_condition, module_condition=module_condition
	)


def has_permission(doc, ptype, user):
	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return True

	if doc.type == "Report":
		if doc.report_name in get_allowed_report_names():
			return True
	else:
		allowed_doctypes = tuple(frappe.permissions.get_doctypes_with_read())
		if doc.document_type in allowed_doctypes:
			return True

	return False


@frappe.whitelist()
def get_result(doc, filters, to_date=None):
	doc = frappe.parse_json(doc)
	fields = []
	sql_function_map = {
		"Count": "count",
		"Sum": "sum",
		"Average": "avg",
		"Minimum": "min",
		"Maximum": "max",
	}

	function = sql_function_map[doc.function]

	if function == "count":
		fields = [f"{function}(*) as result"]
	else:
		fields = [
			"{function}({based_on}) as result".format(
				function=function, based_on=doc.aggregate_function_based_on
			)
		]

	if not filters:
		filters = []
	elif isinstance(filters, str):
		filters = frappe.parse_json(filters)

	if to_date:
		filters.append([doc.document_type, "creation", "<", to_date])

	res = frappe.get_list(
		doc.document_type, fields=fields, filters=filters, parent_doctype=doc.parent_document_type
	)
	number = res[0]["result"] if res else 0

	return flt(number)


@frappe.whitelist()
def get_percentage_difference(doc, filters, result):
	doc = frappe.parse_json(doc)
	result = frappe.parse_json(result)

	doc = frappe.get_doc("Number Card", doc.name)

	if not doc.get("show_percentage_stats"):
		return

	previous_result = calculate_previous_result(doc, filters)
	if previous_result == 0:
		return None
	else:
		if result == previous_result:
			return 0
		else:
			return ((result / previous_result) - 1) * 100.0


def calculate_previous_result(doc, filters):
	from frappe.utils import add_to_date

	current_date = frappe.utils.now()
	if doc.stats_time_interval == "Daily":
		previous_date = add_to_date(current_date, days=-1)
	elif doc.stats_time_interval == "Weekly":
		previous_date = add_to_date(current_date, weeks=-1)
	elif doc.stats_time_interval == "Monthly":
		previous_date = add_to_date(current_date, months=-1)
	else:
		previous_date = add_to_date(current_date, years=-1)

	number = get_result(doc, filters, previous_date)
	return number


@frappe.whitelist()
def create_number_card(args):
	args = frappe.parse_json(args)
	doc = frappe.new_doc("Number Card")

	doc.update(args)
	doc.insert(ignore_permissions=True)
	return doc


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_cards_for_user(doctype, txt, searchfield, start, page_len, filters):
	meta = frappe.get_meta(doctype)
	searchfields = meta.get_search_fields()
	search_conditions = []

	if not frappe.db.exists("DocType", doctype):
		return

	numberCard = DocType("Number Card")

	if txt:
		search_conditions = [numberCard[field].like(f"%{txt}%") for field in searchfields]

	condition_query = frappe.qb.get_query(
		doctype,
		filters=filters,
		validate_filters=True,
	)

	return (
		condition_query.select(numberCard.name, numberCard.label, numberCard.document_type)
		.where((numberCard.owner == frappe.session.user) | (numberCard.is_public == 1))
		.where(Criterion.any(search_conditions))
	).run()


@frappe.whitelist()
def create_report_number_card(args):
	card = create_number_card(args)
	args = frappe.parse_json(args)
	args.name = card.name
	if args.dashboard:
		add_card_to_dashboard(frappe.as_json(args))


@frappe.whitelist()
def add_card_to_dashboard(args):
	args = frappe.parse_json(args)

	dashboard = frappe.get_doc("Dashboard", args.dashboard)
	dashboard_link = frappe.new_doc("Number Card Link")
	dashboard_link.card = args.name

	if args.set_standard and dashboard.is_standard:
		card = frappe.get_doc("Number Card", dashboard_link.card)
		card.is_standard = 1
		card.module = dashboard.module
		card.save()

	dashboard.append("cards", dashboard_link)
	dashboard.save()
