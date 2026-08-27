import io
import json
import os
import shutil
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.utils.data import cstr
from frappe.utils.pdf import get_host_url

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

	return {
		"options": options,
		"is_print_designer": bool(
			print_format and frappe.get_cached_value("Print Format", print_format, "print_designer")
		),
		"host_url": get_host_url(),
		"bench_sites_path": os.path.join(frappe.utils.get_bench_path(), "sites"),
		"site_public_path": frappe.get_site_path("public"),
		"default_page_size": print_settings.pdf_page_size or "A4",
		"default_page_height": _page_dimension(print_settings.pdf_page_height),
		"default_page_width": _page_dimension(print_settings.pdf_page_width),
	}


def _page_dimension(value) -> str | None:
	return cstr(value) if value else None


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

	pdf = render(html, build_config(print_format, options))

	if password:
		pdf = encrypt(pdf, password)

	return pdf
