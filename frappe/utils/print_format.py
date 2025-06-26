import http
import json
from math import log
import os
import uuid
import re
from io import BytesIO
from typing import Literal

from frappe.contacts.doctype.address.address import get_address_display_list
from pypdf import PdfWriter

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.translate import print_language
from frappe.utils.deprecations import deprecated
from frappe.utils.pdf import get_pdf

no_cache = 1

base_template_path = "www/printview.html"
standard_format = "templates/print_formats/standard.html"

from frappe.www.printview import (
	capitalize_first_letter,
	filter_customer,
	format_dates,
	validate_print_permission
)


@frappe.whitelist()
def download_multi_pdf(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
):
	return _download_multi_pdf(doctype, name, format, no_letterhead, letterhead, options)


@frappe.whitelist()
def download_multi_pdf_async(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
):
	task_id = str(uuid.uuid4())
	if isinstance(doctype, dict):
		doc_count = sum([len(doctype[dt]) for dt in doctype])
	else:
		doc_count = len(json.loads(name))

	frappe.enqueue(
		_download_multi_pdf,
		doctype=doctype,
		name=name,
		task_id=task_id,
		format=format,
		no_letterhead=no_letterhead,
		letterhead=letterhead,
		options=options,
		queue="long" if doc_count > 20 else "short",
	)
	frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
	return {"task_id": task_id}


def _download_multi_pdf(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
	task_id: str | None = None,
):
	filename = ""
	pdf_writer = PdfWriter()

	if isinstance(options, str):
		options = json.loads(options)

	if not isinstance(doctype, dict):
		result = json.loads(name)
		total_docs = len(result)
		filename = f"{doctype}_"

		for idx, ss in enumerate(result):
			try:
				pdf_writer = frappe.get_print(
					doctype,
					ss,
					format,
					as_pdf=True,
					output=pdf_writer,
					no_letterhead=no_letterhead,
					letterhead=letterhead,
					pdf_options=options,
				)
			except Exception:
				if task_id:
					frappe.publish_realtime(task_id=task_id, message={"message": "Failed"})

			if task_id:
				frappe.publish_progress(
					percent=(idx + 1) / total_docs * 100,
					title=_("PDF Generation in Progress"),
					description=_("{0}/{1} complete | Please leave this tab open until completion.").format(
						idx + 1, total_docs
					),
					task_id=task_id,
				)

		if task_id is None:
			frappe.local.response.filename = "{doctype}.pdf".format(
				doctype=doctype.replace(" ", "-").replace("/", "-")
			)

	else:
		total_docs = sum([len(doctype[dt]) for dt in doctype])
		count = 1
		for doctype_name in doctype:
			filename += f"{doctype_name}_"
			for doc_name in doctype[doctype_name]:
				try:
					pdf_writer = frappe.get_print(
						doctype_name,
						doc_name,
						format,
						as_pdf=True,
						output=pdf_writer,
						no_letterhead=no_letterhead,
						letterhead=letterhead,
						pdf_options=options,
					)
				except Exception:
					if task_id:
						frappe.publish_realtime(task_id=task_id, message="Failed")
					frappe.log_error(
						title="Error in Multi PDF download",
						message=f"Permission Error on doc {doc_name} of doctype {doctype_name}",
						reference_doctype=doctype_name,
						reference_name=doc_name,
					)

				count += 1

				if task_id:
					frappe.publish_progress(
						percent=count / total_docs * 100,
						title=_("PDF Generation in Progress"),
						description=_(
							"{0}/{1} complete | Please leave this tab open until completion."
						).format(count, total_docs),
						task_id=task_id,
					)
		if task_id is None:
			frappe.local.response.filename = f"{name}.pdf"

	with BytesIO() as merged_pdf:
		pdf_writer.write(merged_pdf)
		if task_id:
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"{filename}{task_id}.pdf",
					"content": merged_pdf.getvalue(),
					"is_private": 1,
				}
			)
			_file.save()
			frappe.publish_realtime(f"task_complete:{task_id}", message={"file_url": _file.unique_url})
		else:
			frappe.local.response.filecontent = merged_pdf.getvalue()
			frappe.local.response.type = "pdf"


@deprecated
def read_multi_pdf(output: PdfWriter) -> bytes:
	with BytesIO() as merged_pdf:
		output.write(merged_pdf)
		return merged_pdf.getvalue()


def format_address_detail_to_print(text):
    # Si no viene un diccionario, devolvemos cadena vacía
    if not isinstance(text, dict):
        return ""

    # Helper seguro: strip solo si es str y no está vacío
    def safe_strip(val):
        return val.strip() if isinstance(val, str) and val.strip() else None

    # Campos limpiados
    address     = safe_strip(text.get("address_line1"))
    address2    = safe_strip(text.get("address_line2"))
    zip_code    = safe_strip(text.get("pincode"))
    city        = safe_strip(text.get("city"))
    country_raw = text.get("country")
    country     = _(safe_strip(country_raw)) if country_raw else None

    # Construir la lista de líneas de la dirección
    parts = []
    if address:
        parts.append(address)
    if address2:
        parts.append(address2)

    # Línea combinada: [pincode] [city]
    zip_city = " ".join(filter(None, [zip_code, city]))
    if zip_city:
        parts.append(zip_city)

    # País en su propia línea (opcional)
    if country:
        parts.append(country)

    # Unir con <br> sin líneas vacías intermedias
    return "<br>".join(parts)


def convert_to_int(value):
	try:
		return int(float(value))
	except ValueError:
		raise ValueError("The input value is not a number or a numeric string")


def convert_to_float(value):
	try:
		return float(value)
	except ValueError:
		raise ValueError("The input value is not a number or a numeric string")


@frappe.whitelist(allow_guest=True)
def download_pdf(
	doctype: str,
	name: str,
	format=None,
	doc=None,
	no_letterhead=0,
	language=None,
	letterhead=None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
):
	doc = doc or frappe.get_doc(doctype, name)
	original_customer_name = ""

	if doc.get("customer_name"):
		original_customer_name = doc.get("original_customer_name")
		doc.original_customer_name = doc.get("customer_name")
		doc.customer_name = capitalize_first_letter(doc.get("customer_name"))

	if doc.get("doctype") in ["Quotation", "Sales Invoice"]:
		if original_customer_name:
			customers = frappe.db.sql(
				"""
				SELECT name, customer_name
				FROM `tabCustomer` cust
				WHERE cust.customer_name = %(name_pattern)s
				""",
				{"name_pattern": original_customer_name},
				as_dict=1,
			)
			if len(customers):
				customer_filtered = filter_customer(customers, original_customer_name)
				if customer_filtered:
					customer_filtered_name = customer_filtered.name
					address_records = get_address_display_list("Customer", customer_filtered_name)

					if address_records and isinstance(address_records, list):
						billing_address = next((address for address in address_records if address.get("address_type") == "Billing" and address.get("disabled") == 0), None)
						shipping_address = next((address for address in address_records if address.get("address_type") == "Shipping" and address.get("disabled") == 0), None)
						selected_address = billing_address or shipping_address or address_records[0]
					else:
						selected_address = None

					doc.address_display = format_address_detail_to_print(selected_address)
				else:
					doc.address_display = ""

	items_custom = []
	if doc.get("doctype") in ["Quotation", "Sales Invoice"]:
		for item in doc.get("items"):
			if doc.get("doctype") == "Sales Invoice":
				value = frappe.get_doc("Sales Invoice Item", item.name)
			elif doc.get("doctype") == "Quotation":
				value = frappe.get_doc("Quotation Item", item.name)
			items_custom.append({
				"item_code": value.get("item_code"),
				"item_name": value.get("item_name"),
				"description": value.get("description"),
				"brand": value.get("brand"),
				"base_amount": value.get("base_amount", 0),
				"tvs_pn": value.get("tvs_pn") or "",
				"qty": convert_to_float(value.get("qty")),
				"rate": value.get("rate", 0),
			})
		doc.items_custom = items_custom

	if doc.get("base_total") is not None:
		doc.base_total = "{:.2f}".format(doc.get("base_total"))

	if doc.get("base_total_taxes_and_charges") is not None:
		doc.base_total_taxes_and_charges = "{:.2f}".format(doc.get("base_total_taxes_and_charges"))

	if doc.get("grand_total") is not None:
		doc.grand_total = "{:.2f}".format(doc.get("grand_total"))

	if doc.get("doctype") == "Sales Invoice":
		doc.posting_date_custom = format_dates(doc.get("posting_date"))
		doc.due_date_custom = format_dates(doc.get("due_date"))

	if doc.get("doctype") == "Quotation":
		doc.transaction_date_custom = format_dates(doc.get("transaction_date"))
		doc.valid_till_custom = format_dates(doc.get("valid_till"))

	validate_print_permission(doc)

	with print_language(language):
		pdf_file = frappe.get_print(
			doctype,
			name,
			format,
			doc=doc,
			as_pdf=True,
			letterhead=letterhead,
			no_letterhead=no_letterhead,
			pdf_generator=pdf_generator,
		)

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf_file
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def report_to_pdf(html, orientation="Landscape"):
	make_access_log(file_type="PDF", method="PDF", page=html)
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def print_by_server(
	doctype, name, printer_setting, print_format=None, doc=None, no_letterhead=0, file_path=None
):
	print_settings = frappe.get_doc("Network Printer Settings", printer_setting)
	try:
		import cups
	except ImportError:
		frappe.throw(_("You need to install pycups to use this feature!"))

	try:
		cups.setServer(print_settings.server_ip)
		cups.setPort(print_settings.port)
		conn = cups.Connection()
		output = PdfWriter()
		output = frappe.get_print(
			doctype, name, print_format, doc=doc, no_letterhead=no_letterhead, as_pdf=True, output=output
		)
		if not file_path:
			file_path = os.path.join("/", "tmp", f"frappe-pdf-{frappe.generate_hash()}.pdf")
		output.write(open(file_path, "wb"))
		conn.printFile(print_settings.printer_name, file_path, name, {})
	except OSError as e:
		if any(error in str(e) for error in [
			"ContentNotFoundError",
			"ContentOperationNotPermittedError",
			"UnknownContentError",
			"RemoteHostClosedError"
		]):
			frappe.throw(_("PDF generation failed"))
	except cups.IPPError:
		frappe.throw(_("Printing failed"))
