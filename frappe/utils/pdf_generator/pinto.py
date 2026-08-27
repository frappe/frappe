import io
import json
import os
import shutil
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.utils.data import cstr
from frappe.utils.pdf import get_host_url, inline_private_images

GENERATOR = "pinto"
DEFAULT_TIMEOUT = 120


class PintoNotFound(frappe.ValidationError):
	pass


class PintoRenderError(frappe.ValidationError):
	pass


def get_pinto_path() -> str:
	"""Resolve the `pinto` binary: site config `pinto_path`, else `pinto` on PATH."""
	binary = frappe.conf.get("pinto_path") or shutil.which(GENERATOR)

	if not binary or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
		frappe.throw(
			_("pinto binary not found at {0}. Install it or set `pinto_path` in site config.").format(
				frappe.bold(binary or GENERATOR)
			),
			exc=PintoNotFound,
			title=_("PDF Generator Unavailable"),
		)

	return binary


def build_config(print_format: str | None, options: dict) -> dict:
	"""The `--options` payload pinto expects: the wkhtmltopdf-style options plus the
	site-local values a standalone binary cannot read for itself."""
	print_settings = frappe.get_cached_doc("Print Settings")
	page_size, page_options = resolve_page_size(print_settings, options)

	return {
		"options": {**options, **page_options},
		"is_print_designer": bool(
			print_format and frappe.get_cached_value("Print Format", print_format, "print_designer")
		),
		"host_url": get_host_url(),
		"bench_sites_path": os.path.join(frappe.utils.get_bench_path(), "sites"),
		"site_public_path": frappe.get_site_path("public"),
		"default_page_size": page_size,
	}


def resolve_page_size(print_settings, options: dict) -> tuple[str, dict]:
	"""Mirror `prepare_options`: turn a "Custom" page size into explicit dimensions.

	pinto resolves geometry from `page-size`/`page-width`/`page-height` only — it has no
	notion of the "Custom" sentinel, and reads bare Print Settings dimensions as pixels.
	"""
	page_size = options.get("page-size") or print_settings.pdf_page_size or "A4"
	if page_size != "Custom":
		return page_size, {}

	dimensions = {}
	for option, field in (("page-height", "pdf_page_height"), ("page-width", "pdf_page_width")):
		value = options.get(option) or print_settings.get(field)
		if value:
			dimensions[option] = with_unit(value)

	return "A4", dimensions


def with_unit(value, unit: str = "mm") -> str:
	"""Print Settings stores page dimensions as bare floats; CSS lengths need a unit."""
	value = cstr(value).strip()
	return value if value[-1:].isalpha() else f"{value}{unit}"


def render(html: str, config: dict) -> bytes:
	"""Pipe the printview HTML through pinto and return the PDF bytes."""
	binary = get_pinto_path()

	with tempfile.TemporaryDirectory() as tmp:
		config_path = os.path.join(tmp, "config.json")
		with open(config_path, "w", encoding="utf-8") as f:
			json.dump(config, f)

		try:
			result = subprocess.run(
				[binary, "--html", "-", "--options", config_path, "--out", "-"],
				input=html.encode("utf-8"),
				capture_output=True,
				timeout=frappe.conf.get("pinto_timeout") or DEFAULT_TIMEOUT,
				check=True,
			)
		except subprocess.TimeoutExpired:
			frappe.throw(
				_("pinto timed out while rendering the PDF."),
				exc=PintoRenderError,
				title=_("PDF Generation Failed"),
			)
		except subprocess.CalledProcessError as e:
			frappe.throw(
				_("pinto failed to render the PDF: {0}").format(_stderr(e)),
				exc=PintoRenderError,
				title=_("PDF Generation Failed"),
			)

	if not result.stdout.startswith(b"%PDF"):
		frappe.throw(_("pinto returned an invalid PDF."), exc=PintoRenderError)

	return result.stdout


def _stderr(e: subprocess.CalledProcessError) -> str:
	return (e.stderr or b"").decode("utf-8", "replace").strip() or _("exit code {0}").format(e.returncode)


def encrypt(pdf: bytes, password: str) -> bytes:
	from pypdf import PdfReader, PdfWriter

	writer = PdfWriter()
	writer.append_pages_from_reader(PdfReader(io.BytesIO(pdf)))
	writer.encrypt(password)

	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def get_pinto_pdf(print_format, html, options, output=None, pdf_generator=None):
	"""`pdf_generator` hook: renders printview HTML to PDF in-process via the `pinto` binary.

	Beta-renderer formats dispatch through this hook without HTML; they are pinned to
	Chromium, so hand them back untouched.
	"""
	if pdf_generator != GENERATOR or not html:
		return

	options = dict(options or {})
	password = options.pop("password", None)

	pdf = render(inline_private_images(html), build_config(print_format, options))

	# An `output` writer merges the pages downstream and cannot read an encrypted PDF;
	# wkhtmltopdf skips encryption in the same case.
	if password and not output:
		pdf = encrypt(pdf, password)

	return pdf
