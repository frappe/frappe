# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Emit Typst markup from a resolved print format layout.

The emitter consumes the SAME layout `PrintFormatGenerator` renders HTML from —
after normalise_layout, permlevel stripping, visibility conditions and table
column pruning — so the two renderers can never disagree on what a user is
allowed to see. Typst receives only resolved data and geometry, never logic.

Formats that use features Typst cannot express (raw HTML blocks, Jinja field
templates, client-side barcodes, …) are refused by :func:`typst_blockers`;
they keep rendering through Chromium.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils.html_utils import unescape_html

#: px (builder/CSS space) → pt (Typst space)
PX_TO_PT = 0.75

#: the hairline stroke and muted ink every surface shares
HAIRLINE = '0.6pt + rgb("#e5e7eb")'
MUTED = "#6b7280"


def pt(px, default=0.0) -> float:
	"""A px value from the builder as Typst points; `default` fills empty/zero."""
	return round((frappe.utils.flt(px) or default) * PX_TO_PT, 2)


#: field types that disqualify a format — each with the reason shown to the user
# translated at use, not import — a module-level _() would pin the first site's language
# mirrored client-side in print_format_builder/utils.js typst_blockers_client
BLOCKER_FIELDTYPES = {
	"HTML": "Custom HTML block",
	"Field Template": "Field Template (Jinja HTML)",
	"Linked Field": "Linked Field",
	"Summary Table": "Summary Table",
}

PAGE_NUMBER_POSITIONS = {
	"Top Left": ("header", "left"),
	"Top Center": ("header", "center"),
	"Top Right": ("header", "right"),
	"Bottom Left": ("footer", "left"),
	"Bottom Center": ("footer", "center"),
	"Bottom Right": ("footer", "right"),
}

RIGHT_ALIGNED_FIELDTYPES = frozenset({"Currency", "Float", "Int", "Percent"})

#: color keywords valid in both CSS and Typst — any other name is a blocker,
#: because Typst treats it as an undefined variable and the whole compile fails
TYPST_NAMED_COLORS = frozenset(
	"black gray silver white navy blue aqua teal purple fuchsia maroon red orange yellow olive green lime".split()
)

#: the css properties the builder writes into custom_style that we can express in
#: Typst; anything outside this list keeps the format on Chromium
TRANSLATABLE_STYLE_PROPS = frozenset(
	{
		"font-weight",
		"border-top",
		"border-bottom",
		"margin-top",
		"padding-top",
		"padding-bottom",
		"flex-direction",
		"align-items",
		"gap",
	}
)


def translate_custom_style(style: str) -> tuple[dict, list[str]]:
	"""Map a declaration list onto Typst effects; unknown properties are returned,
	never dropped — a property we cannot express keeps the format on Chromium."""
	effects, unknown = {}, []
	for declaration in (style or "").split(";"):
		if ":" not in declaration:
			continue
		prop, value = (part.strip() for part in declaration.split(":", 1))
		prop = prop.lower()
		if prop not in TRANSLATABLE_STYLE_PROPS:
			unknown.append(prop)
			continue
		if prop == "font-weight":
			if value in ("bold", "600", "700", "800", "900"):
				effects["bold"] = True
			else:
				unknown.append(f"{prop}: {value}")
		elif prop in ("border-top", "border-bottom"):
			match = re.match(r"(\d+(?:\.\d+)?)px\s+\w+\s+(#(?:[0-9a-fA-F]{3}){1,2}|[a-z]+)$", value)
			color = match and match.group(2)
			if match and (color.startswith("#") or color in TYPST_NAMED_COLORS):
				width = pt(match.group(1))
				paint = f'rgb("{color}")' if color.startswith("#") else color
				effects["stroke_top" if prop == "border-top" else "stroke_bottom"] = f"{width}pt + {paint}"
			else:
				unknown.append(f"{prop}: {value}")
		elif prop in ("margin-top", "padding-top", "padding-bottom", "gap"):
			match = re.match(r"(\d+(?:\.\d+)?)(px)?$", value)
			if match:
				key = {
					"margin-top": "space_before",
					"padding-top": "inset_top",
					"padding-bottom": "inset_bottom",
					"gap": "gap",
				}[prop]
				effects[key] = pt(match.group(1))
			else:
				unknown.append(f"{prop}: {value}")
		# flex-direction / align-items describe what the structured layout
		# already does — accepted so they never block, nothing to emit
	return effects, unknown


def typst_blockers(print_format, layout) -> list[str]:
	"""Why this format cannot render through Typst — empty means it can.

	The single authority: the builder UI mirrors this to grey out the option,
	and render_pdf refuses when it is non-empty."""
	blockers = []
	if print_format.get("custom_format"):
		blockers.append(_("Custom HTML format"))
		return blockers
	if not print_format.get("print_format_builder_beta"):
		blockers.append(_("Not a builder format"))
		return blockers
	if (print_format.get("css") or "").strip():
		blockers.append(_("Custom CSS on the format"))

	if not isinstance(layout, dict):
		return blockers

	letter_head = layout.get("letter_head")
	if letter_head:
		lh = frappe.db.get_value(
			"Letter Head",
			letter_head,
			["source", "image", "content", "custom_css", "footer_source", "footer", "footer_image"],
			as_dict=True,
		)
		blockers.extend(letterhead_blockers(lh))

	for key in _COLOR_KEYS:
		value = print_format.get(key)
		if value and not safe_color(value):
			blockers.append(_("Format color Typst can't render: {0}").format(value))

	seen = set()
	for where, node in _walk(layout):
		style = node.get("custom_style")
		if isinstance(style, str) and style.strip():
			_effects, unknown = translate_custom_style(style)
			if unknown:
				key = ("custom_style", where)
				if key not in seen:
					seen.add(key)
					blockers.append(_("Untranslatable CSS on {0}: {1}").format(where, ", ".join(unknown)))
		fieldtype_reason = BLOCKER_FIELDTYPES.get(node.get("fieldtype"))
		reason = (
			(_(fieldtype_reason) if fieldtype_reason else None)
			or _barcode_blocker(node, print_format)
			or _image_blocker(node)
			or _color_blocker(node)
		)
		if reason and reason not in seen:
			seen.add(reason)
			blockers.append(reason)
	return blockers


def _barcode_blocker(df, print_format):
	"""Only QR renders server-side; JsBarcode formats need a browser."""
	if df.get("fieldtype") != "Barcode":
		return None
	if df.get("custom"):
		return None if df.get("barcode_format") == "QR" else _("Barcode (non-QR)")
	try:
		meta_df = frappe.get_meta(print_format.doc_type).get_field(df.get("fieldname"))
	except Exception:
		meta_df = None
	from frappe.utils.print_format_generator import is_qr_barcode_options

	if meta_df and is_qr_barcode_options(meta_df.options):
		return None
	return _("Barcode (non-QR)")


def letterhead_blockers(lh) -> list[str]:
	"""Image letter heads render natively; only HTML sides block."""
	if not lh:
		return []
	blockers = []
	if (lh.get("custom_css") or "").strip():
		blockers.append(_("Letterhead with custom CSS"))
	header_is_image = lh.get("source") == "Image" and lh.get("image")
	if (lh.get("content") or "").strip() and not header_is_image:
		blockers.append(_("Letterhead with HTML content"))
	footer_is_image = lh.get("footer_source") == "Image" and lh.get("footer_image")
	if (lh.get("footer") or "").strip() and not footer_is_image:
		blockers.append(_("Letterhead footer with HTML content"))
	for image in (header_is_image and lh.get("image"), footer_is_image and lh.get("footer_image")):
		if image and str(image).startswith(("http://", "https://")):
			blockers.append(_("Letterhead with a remote image URL"))
			break
	return blockers


def _image_blocker(df):
	if df.get("fieldtype") != "Image":
		return None
	src = df.get("image_url") or ""
	if src.startswith(("http://", "https://")):
		return _("Remote image URL")
	return None


#: color fields Typst emits through rgb("#..."); a non-hex value (named color,
#: rgb()/hsl()) would abort the compile, so it's gated instead of silently dropped
_COLOR_KEYS = ("label_color", "value_color")


def _color_blocker(df):
	for key in _COLOR_KEYS:
		value = df.get(key)
		if value and not safe_color(value):
			return _("Field color Typst can't render: {0}").format(value)
	return None


def has_typst_blocks(layout) -> bool:
	"""True when the layout carries raw Typst markup — such a format can only
	render through Typst, the mirror image of what blocks Typst itself.
	An empty block emits nothing, so it doesn't pin the renderer."""
	if not isinstance(layout, dict):
		return False
	return any(
		df.get("fieldtype") == "Typst" and (df.get("typst") or "").strip() for _where, df in _walk(layout)
	)


def _walk(layout):
	zones = [
		(_("Header"), layout.get("header")),
		(_("Footer"), layout.get("footer")),
	] + [(s.get("label") or _("Section"), s) for s in layout.get("sections") or [] if isinstance(s, dict)]
	for where, zone in zones:
		if not isinstance(zone, dict):
			continue
		yield where, zone
		for column in zone.get("columns") or []:
			for df in (column or {}).get("fields") or []:
				if isinstance(df, dict):
					yield where, df


def typst_font_paths() -> list[str]:
	"""Directories Typst loads fonts from — the site's cache plus system fonts."""
	import os

	path = frappe.get_site_path("private", "files", "typst_fonts")
	return [os.path.abspath(path)] if os.path.isdir(path) else []


def compile_typst_source(source: str) -> bytes:
	"""Compile standalone Typst markup in a confined tempdir, against the same
	font set prints use."""
	import os
	import tempfile

	import typst

	with tempfile.TemporaryDirectory() as tmp:
		path = os.path.join(tmp, "main.typ")
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(path, "w") as f:
			f.write(source)
		return typst.compile(path, root=tmp, font_paths=typst_font_paths())


def ensure_typst_fonts(family: str | None):
	"""Fetch the format's Google Font as TTFs into the site's font cache.

	Best-effort: offline or unknown families log once and Typst falls back to
	its bundled font instead of failing the print."""
	import os

	if not family or family == "Default":
		return
	safe_family = re.sub(r"[^A-Za-z0-9 _-]", "", family).replace(" ", "_")
	if not safe_family:
		return
	import time

	root = frappe.get_site_path("private", "files", "typst_fonts")
	target = os.path.join(root, safe_family)
	if os.path.isdir(target) and os.listdir(target):
		return
	# a failed family is not retried for a day — the fetch sits on the render
	# path and an offline site must not pay the timeouts on every print
	sentinel = os.path.join(root, f".{safe_family}.unavailable")
	if os.path.exists(sentinel) and time.time() - os.path.getmtime(sentinel) < 86400:
		return

	def mark_unavailable():
		os.makedirs(root, exist_ok=True)
		# safe_family is allowlist-sanitized above; the path cannot leave the cache dir
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(sentinel, "w"):
			pass

	try:
		import requests

		urls = []
		for weight in (400, 500, 600, 700):
			css = requests.get(
				"https://fonts.googleapis.com/css2",
				params={"family": f"{family}:wght@{weight}"},
				headers={"User-Agent": "Mozilla/4.0"},
				timeout=5,
			).text
			found = re.findall(r"https://[^)]+\.ttf", css)
			if found:
				urls.append((weight, found[0]))
		if not urls:
			mark_unavailable()
			return
		# fetch into a scratch dir and rename once complete — a download that
		# dies halfway must not leave a half-populated cache that looks done
		scratch = f"{target}.partial-{os.getpid()}"
		os.makedirs(scratch, exist_ok=True)
		try:
			for weight, url in urls:
				ttf = requests.get(url, timeout=10).content
				# safe_family is allowlist-sanitized above; the path cannot leave the cache dir
				# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
				with open(os.path.join(scratch, f"{safe_family}-{weight}.ttf"), "wb") as f:
					f.write(ttf)
			if not os.path.isdir(target):
				os.rename(scratch, target)
		finally:
			if os.path.isdir(scratch):
				import shutil

				shutil.rmtree(scratch, ignore_errors=True)
	except Exception:
		mark_unavailable()
		frappe.log_error(title=f"Typst font fetch failed: {family}")


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def q(value) -> str:
	"""A Typst string literal — every doc value crosses as a quoted string, so
	document content can never be interpreted as Typst markup. ensure_ascii stays
	off because Typst reads \\uXXXX as literal text, not an escape; C0 controls go
	because JSON escapes like \\f are not valid Typst escapes."""
	text = _CONTROL_CHARS.sub("", str(value if value is not None else ""))
	return json.dumps(text, ensure_ascii=False)


#: every character Typst assigns meaning to in markup mode — Typst accepts a
#: backslash escape for any punctuation, so escaping renders each literally
_TYPST_SPECIALS = re.compile(r"([\\#$*_\[\]`~'\"@<>/=+-])")


class TypstRaw(str):
	"""A Jinja value that must reach Typst unescaped: {{ x | typst_raw }}."""


def typst_escape(value):
	if isinstance(value, TypstRaw):
		return str(value)
	text = _CONTROL_CHARS.sub("", str(value if value is not None else ""))
	return _TYPST_SPECIALS.sub(r"\\\1", text)


def render_typst_template(markup: str, context: dict) -> str:
	"""Jinja for Typst blocks — every interpolated value is escaped so document
	content crosses as text, never as Typst code; the markup around it stays raw."""
	from frappe.utils.jinja import get_jenv

	env = get_jenv().overlay(finalize=typst_escape, autoescape=False)
	env.filters = env.filters.copy()
	env.filters["typst_raw"] = TypstRaw
	return env.from_string(markup).render(context)


def has_jinja(markup: str) -> bool:
	return "{{" in markup or "{%" in markup


# exactly the lengths Typst's rgb() accepts — a 5/7-digit string would abort the compile
COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def safe_color(value, default=None):
	if isinstance(value, str) and COLOR_PATTERN.fullmatch(value.strip()):
		return value.strip()
	return default


def muted_text(text, color=MUTED) -> str:
	return f'#text(size: 0.85em, fill: rgb("{color}"), {q(text)})'


def _aligned(body: str, align) -> str:
	if body and align in ("center", "right"):
		return f"#align({align})[{body}]"
	return body


def _fr_widths(columns) -> list[str]:
	widths = []
	for col in columns:
		width = frappe.utils.flt(col.get("width"))
		widths.append(f"{round(width, 2)}fr" if width else "1fr")
	return widths


def _text_value(html_ish: str) -> str:
	"""Formatted values may carry markup (Text Editor, address_display); keep the
	line structure, drop the tags."""
	value = str(html_ish or "")
	if "<" not in value:
		return value
	value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
	value = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", value, flags=re.I)
	value = frappe.utils.strip_html(value)
	return unescape_html(value).strip()


class TypstEmitter:
	def __init__(self, generator):
		self.generator = generator
		self.doc = generator.doc
		self.print_format = generator.print_format
		self.layout = generator.layout
		self.assets: dict[str, bytes] = {}
		self._embedded: dict[str, str | None] = {}

	# ── document ────────────────────────────────────────────────

	def prepare(self):
		"""Render zones and body once; assets register as a side effect."""
		if hasattr(self, "header_src"):
			return
		lh = getattr(self.generator, "letterhead", None)
		header_zone = self.layout.get("header")
		self.header_src = self._section(header_zone, zone=True) if isinstance(header_zone, dict) else ""
		lh_header = self._letterhead_image(lh, "header")
		if lh_header:
			self.header_src = "\n".join(p for p in (lh_header, self.header_src) if p)
		self.body_src = "\n".join(
			part for part in (self._section(s) for s in self.layout.get("sections") or []) if part
		)
		footer_zone = self.layout.get("footer")
		self.footer_src = self._section(footer_zone, zone=True) if isinstance(footer_zone, dict) else ""
		lh_footer = self._letterhead_image(lh, "footer")
		if lh_footer:
			self.footer_src = "\n".join(p for p in (self.footer_src, lh_footer) if p)

	def _letterhead_image(self, lh, side) -> str:
		if not lh:
			return ""
		prefix = "" if side == "header" else "footer_"
		if lh.get(f"{prefix}source") != "Image":
			return ""
		src = lh.get(f"{prefix}image")
		if not src:
			return ""
		name = self._embed_image(src)
		if name is None:
			# an unreadable letterhead image degrades like a dead <img> in the
			# HTML render — a permission gap must not break every print
			return ""
		args = [f'"{name}"']
		width = frappe.utils.flt(lh.get(f"{prefix}image_width"))
		height = frappe.utils.flt(lh.get(f"{prefix}image_height"))
		if width:
			args.append(f"width: {pt(width)}pt")
		elif height:
			args.append(f"height: {pt(height)}pt")
		body = f"#image({', '.join(args)})"
		return _aligned(body, (lh.get(f"{prefix}align") or "Left").lower())

	def _page_size_mm(self) -> tuple[float, float]:
		"""(width, height) in mm for the site's configured paper, mirroring the
		Chromium path's PageSize map so both renderers agree on geometry. Custom
		sizes fall back to A4 — their cross-renderer unit contract is ambiguous."""
		from frappe.utils.pdf_generator.browser import PageSize

		ps = getattr(self.generator, "print_settings", None)
		size = (ps and ps.get("pdf_page_size")) or frappe.db.get_single_value(
			"Print Settings", "pdf_page_size"
		)
		dims = PageSize.get(size) if size and size != "Custom" else None
		return (dims["width"], dims["height"]) if dims else (210, 297)

	def measure_source(self) -> str:
		"""A document whose only output is the measured height of each zone, read
		back with typst.query — how the top/bottom margins learn to make room."""
		self.prepare()
		pf = self.print_format
		page_width, page_height = self._page_size_mm()
		inner = round(
			page_width - (frappe.utils.flt(pf.margin_left) or 15) - (frappe.utils.flt(pf.margin_right) or 15),
			2,
		)
		lines = [
			f"#set page(width: {page_width}mm, height: {page_height}mm)",
			self._text_setup(),
			"",
		]
		for label, src in (("pfhdr", self.header_src), ("pfftr", self.footer_src)):
			if src:
				lines.append(
					f"#context [#metadata(measure(box(width: {inner}mm)[{src}]).height.pt()) <{label}>]"
				)
		return "\n".join(lines)

	def emit(self, repeat_header_footer=False, header_height_pt=0, footer_height_pt=0):
		"""The document source. With repeat on, the zones move into Typst's page
		header/footer slots (repeated on every page, like Chromium's repeating
		frame) and the margins grow by their measured heights."""
		self.prepare()
		in_page_header = bool(repeat_header_footer and self.header_src)
		in_page_footer = bool(repeat_header_footer and self.footer_src)
		lines = [
			self._page_setup(
				header_zone=self.header_src if in_page_header else None,
				footer_zone=self.footer_src if in_page_footer else None,
				header_height_pt=header_height_pt,
				footer_height_pt=footer_height_pt,
			),
			self._text_setup(),
			"",
		]
		if self.header_src and not in_page_header:
			lines.append(self.header_src)
		lines.append(self.body_src)
		if self.footer_src and not in_page_footer:
			lines.append(self.footer_src)
		return "\n".join(line for line in lines if line), self.assets

	def _page_setup(self, header_zone=None, footer_zone=None, header_height_pt=0, footer_height_pt=0) -> str:
		pf = self.print_format
		top = frappe.utils.flt(pf.margin_top) or 15
		bottom = frappe.utils.flt(pf.margin_bottom) or 15
		top_expr = f"{top}mm + {round(header_height_pt + 12, 2)}pt" if header_zone else f"{top}mm"
		bottom_expr = f"{bottom}mm + {round(footer_height_pt + 12, 2)}pt" if footer_zone else f"{bottom}mm"
		margins = (
			f"(top: {top_expr}, bottom: {bottom_expr}, "
			f"left: {frappe.utils.flt(pf.margin_left) or 15}mm, "
			f"right: {frappe.utils.flt(pf.margin_right) or 15}mm)"
		)
		page_width, page_height = self._page_size_mm()
		args = [f"width: {page_width}mm", f"height: {page_height}mm", f"margin: {margins}"]

		slots = {"header": [], "footer": []}
		position = PAGE_NUMBER_POSITIONS.get(pf.get("page_number") or "")
		if position:
			slot, align = position
			# the translated word must stay literal content — inside a display()
			# pattern, letters like "i" or "v" ("di", "van") count pages
			slots[slot].append(
				f'[#context [#set text(size: 7pt, fill: rgb("{MUTED}"))\n'
				f"  #set align({align})\n"
				f'  #counter(page).display("1")#text({q(" " + _("of") + " ")})#counter(page).final().first()]]'
			)
		if header_zone:
			slots["header"].append(f"[{header_zone}]")
		if footer_zone:
			slots["footer"].insert(0, f"[{footer_zone}]")

		for slot, parts in slots.items():
			if not parts:
				continue
			content = parts[0] if len(parts) == 1 else "stack(spacing: 6pt, " + ", ".join(parts) + ")"
			args.append(f"{slot}: {content}")
			if slot == "header":
				args.append("header-ascent: 8pt" if header_zone else "header-ascent: 30%")
			elif footer_zone:
				args.append("footer-descent: 8pt")
		return "#set page(" + ", ".join(args) + ")"

	def _text_setup(self) -> str:
		pf = self.print_format
		size_pt = pt(pf.font_size, 14)
		args = [f"size: {size_pt}pt"]
		if pf.get("font") and pf.font != "Default":
			args.append(f'font: ({q(pf.font)}, "Libertinus Serif")')
		value_color = safe_color(pf.get("value_color"))
		if value_color:
			args.append(f'fill: rgb("{value_color}")')
		return "#set text(" + ", ".join(args) + ")"

	# ── sections ────────────────────────────────────────────────

	def _section(self, section, zone=False) -> str:
		if section.get("_hidden"):
			return ""
		columns = [c for c in section.get("columns") or [] if isinstance(c, dict)]
		if not columns:
			return ""
		rendered_columns = [self._column(section, c) for c in columns]
		if not any(rendered_columns):
			return ""

		grid = self._columns_grid(section, columns, rendered_columns)
		body = grid
		if section.get("label") and section.get("show_label") != "hide" and not zone:
			label = f"#text(size: 0.9em, weight: 600, {q(_(section['label']))})"
			body = f"#stack(spacing: 8pt,\n[{label}],\n[{body}])"

		block_args = self._section_block_args(section)
		out = f"#block({', '.join(block_args)})[\n{body}\n]"
		out = self._apply_style_effects(out, section.get("custom_style"))
		margin = section.get("margin") or {}
		top = pt(margin.get("top"))
		bottom = pt(margin.get("bottom"))
		# on the html surface custom_style comes after the structured margin in the
		# same style attribute, so a custom margin-top replaces it instead of adding
		if translate_custom_style(section.get("custom_style") or "")[0].get("space_before") is not None:
			top = 0
		if top:
			out = f"#v({top}pt)\n{out}"
		return out + f"\n#v({bottom + 6}pt)"

	def _section_block_args(self, section) -> list[str]:
		args = ["width: 100%"]
		if section.get("field_borders"):
			args.append(f"stroke: {HAIRLINE}")
			args.append("radius: 4pt")
			pad = frappe.utils.flt(section.get("cell_padding"), 0) or 8
			args.append(f"inset: {pt(pad)}pt")
			args.append("clip: true")
		background = safe_color(section.get("background"))
		if background:
			args.append(f'fill: rgb("{background}")')
		padding = section.get("padding") or {}
		if padding and not section.get("field_borders"):
			args.append(
				"inset: (top: {top}pt, bottom: {bottom}pt, left: {left}pt, right: {right}pt)".format(
					**{k: pt(padding.get(k)) for k in ("top", "bottom", "left", "right")}
				)
			)
		if section.get("radius") is not None and not section.get("field_borders"):
			args.append(f"radius: {pt(section['radius'])}pt")
		if section.get("keep_together"):
			args.append("breakable: false")
		return args

	def _columns_grid(self, section, columns, rendered_columns) -> str:
		gap = section.get("gap")
		style_gap = translate_custom_style(section.get("custom_style") or "")[0].get("gap")
		if style_gap is not None:
			gap_pt = style_gap
		else:
			gap_pt = pt(gap if gap is not None else 20)
		widths = _fr_widths(columns)

		justify = section.get("justify")
		cells = [f"[{body or ''}]" for body in rendered_columns]
		if justify in ("space-between", "space-evenly", "center", "right-end"):
			widths = ["auto"] * len(columns)
			if justify == "space-between" and len(columns) > 1:
				spaced = []
				for i, cell in enumerate(cells):
					if i:
						spaced.append("[]")
					spaced.append(cell)
				widths = ["auto", "1fr"] * (len(columns) - 1) + ["auto"]
				cells = spaced
			elif justify == "right-end":
				widths = ["1fr", *(["auto"] * len(columns))]
				cells = ["[]", *cells]
			elif justify == "center":
				widths = ["1fr", *(["auto"] * len(columns)), "1fr"]
				cells = ["[]", *cells, "[]"]
			elif justify == "space-evenly":
				spaced, w = [], []
				for cell in cells:
					spaced += ["[]", cell]
					w += ["1fr", "auto"]
				spaced.append("[]")
				w.append("1fr")
				cells, widths = spaced, w

		if len(cells) == 1:
			return cells[0][1:-1]
		if section.get("field_borders") and section.get("grid_borders") != "rows":
			pad = pt(section.get("cell_padding"), 8)
			# both HTML surfaces force gap to 0 in bordered mode — spacing comes
			# from the cell padding on either side of the divider
			gutter = pad
			divided = [cells[0]]
			for cell in cells[1:]:
				divided.append(f"grid.cell(stroke: (left: {HAIRLINE}), inset: (left: {pad}pt))" + cell)
			return (
				f"#grid(columns: ({', '.join(widths)}), column-gutter: {gutter}pt, align: top,\n"
				+ ",\n".join(divided)
				+ ")"
			)
		return (
			f"#grid(columns: ({', '.join(widths)}), column-gutter: {gap_pt}pt, align: top,\n"
			+ ",\n".join(cells)
			+ ")"
		)

	def _column(self, section, column) -> str:
		parts = [self._field(section, df) for df in column.get("fields") or []]
		parts = [p for p in parts if p]
		if not parts:
			return ""
		if section.get("field_borders") and section.get("grid_borders") != "columns" and len(parts) > 1:
			pad = pt(section.get("cell_padding"), 8)
			ruled = [
				f"#block(width: 100%, stroke: (bottom: {HAIRLINE}), inset: (bottom: {pad}pt))[{p}]"
				for p in parts[:-1]
			] + [parts[-1]]
			return f"#stack(spacing: {pad}pt,\n" + ",\n".join(f"[{p}]" for p in ruled) + ")"
		if len(parts) == 1:
			return parts[0]
		return "#stack(spacing: 8pt,\n" + ",\n".join(f"[{p}]" for p in parts) + ")"

	# ── fields ──────────────────────────────────────────────────

	def _field(self, section, df) -> str:
		if df.get("_hidden"):
			return ""
		body = self._field_body(section, df)
		if not body:
			return ""
		return self._apply_style_effects(body, df.get("custom_style"))

	def _apply_style_effects(self, body: str, style) -> str:
		if not isinstance(style, str) or not style.strip():
			return body
		effects, _unknown = translate_custom_style(style)
		if not effects:
			return body
		if effects.get("bold"):
			body = f"#text(weight: 700)[{body}]"
		strokes = []
		if effects.get("stroke_top"):
			strokes.append(f"top: {effects['stroke_top']}")
		if effects.get("stroke_bottom"):
			strokes.append(f"bottom: {effects['stroke_bottom']}")
		insets = []
		if effects.get("inset_top"):
			insets.append(f"top: {effects['inset_top']}pt")
		if effects.get("inset_bottom"):
			insets.append(f"bottom: {effects['inset_bottom']}pt")
		if strokes or insets:
			args = ["width: 100%"]
			if strokes:
				args.append(f"stroke: ({', '.join(strokes)})")
			if insets:
				args.append(f"inset: ({', '.join(insets)})")
			body = f"#block({', '.join(args)})[{body}]"
		if effects.get("space_before"):
			body = f"#v({effects['space_before']}pt)\n{body}"
		return body

	def _field_body(self, section, df) -> str:
		fieldtype = df.get("fieldtype") or "Data"
		if fieldtype == "Typst":
			return self._typst_block(df)
		if fieldtype == "Divider":
			return '#line(length: 100%, stroke: 0.6pt + rgb("#d1d5db"))'
		if fieldtype == "Spacer":
			height = frappe.utils.flt(df.get("height")) or 13
			return f"#v({pt(height)}pt)"
		if fieldtype == "Table":
			return self._table(df)
		if fieldtype == "Barcode":
			return self._barcode(df)
		if fieldtype in ("Image", "Attach Image"):
			return self._image(df)
		if fieldtype == "Repeater":
			return self._repeater(df)
		if fieldtype == "Static Text":
			return self._static_text(df)
		return self._data_field(section, df)

	def _static_text(self, df) -> str:
		text = (df.get("text") or "").strip()
		if not text:
			return ""
		props = []
		if df.get("bold"):
			props.append('weight: "bold"')
		if df.get("font_size"):
			props.append(f"size: {pt(frappe.utils.flt(df.get('font_size')))}pt")
		body = typst_escape(_(text)).replace("\n", " \\\n")
		out = f"#text({', '.join(props)})[{body}]" if props else typst_escape(_(text))
		if df.get("align") in ("center", "right"):
			out = f"#align({df['align']})[{out}]"
		return out

	def _typst_block(self, df) -> str:
		markup = (df.get("typst") or "").strip()
		if not markup or not has_jinja(markup):
			return markup
		try:
			return render_typst_template(markup, {"doc": self.doc}).strip()
		except Exception as e:
			frappe.throw(
				_("The Typst block could not render its template: {0}").format(str(e)[:300]),
				title=_("Invalid Typst block"),
			)

	def _formatted_value(self, df):
		fieldname = df.get("fieldname")
		if not fieldname:
			return ""
		value = self.doc.get(fieldname)
		# {% if value %} in Data.html gates on the raw value, hiding 0 / 0.0 / False
		if not value:
			return ""
		if df.get("fieldtype") == "Check":
			return _("Yes") if frappe.utils.cint(value) else _("No")
		return _text_value(self.doc.get_formatted(fieldname))

	def _label_color(self, df=None) -> str:
		return (
			(safe_color(df.get("label_color")) if df else None)
			or safe_color(self.print_format.get("label_color"))
			or MUTED
		)

	def _data_field(self, section, df) -> str:
		value = self._formatted_value(df)
		if not value:
			return ""
		show_label = df.get("show_label") or "show"
		inline = show_label == "inline" or section.get("field_orientation") == "left-right"

		label_color = self._label_color(df)
		value_color = safe_color(df.get("value_color"))
		label = ""
		if show_label != "hide" and df.get("label"):
			label = muted_text(_(df["label"]), label_color)
		value_args = [q(value)]
		if value_color:
			value_args.insert(0, f'fill: rgb("{value_color}")')
		value_text = f"#text({', '.join(value_args)})"

		align = df.get("align")
		gap_effect = translate_custom_style(df.get("custom_style") or "")[0].get("gap")
		if inline and label:
			# same precedence as Data.html: custom_style gap overrides label_gap
			gap_pt = gap_effect
			if gap_pt is None:
				gap = df.get("label_gap")
				gap_pt = pt(gap) if gap else 4
			if align in ("right",):
				body = f"#grid(columns: (1fr, auto), column-gutter: {gap_pt}pt, [{label}], [#align(right)[{value_text}]])"
			else:
				body = f"#grid(columns: (auto, 1fr), column-gutter: {gap_pt}pt, [{label}], [{value_text}])"
			return body
		spacing = gap_effect if gap_effect is not None else 4
		parts = [f"[{label}]"] if label else []
		parts.append(f"[{value_text}]")
		body = f"#stack(spacing: {spacing}pt,\n" + ",\n".join(parts) + ")" if len(parts) > 1 else value_text
		return _aligned(body, align)

	def _asset(self, suffix: str, data: bytes) -> str:
		name = f"asset_{len(self.assets)}.{suffix}"
		self.assets[name] = data
		return name

	def _read_site_file(self, src: str) -> bytes | None:
		import base64
		import os

		if src.startswith("data:"):
			try:
				return base64.b64decode(src.split(",", 1)[1])
			except Exception:
				return None
		if src.startswith(("http://", "https://")):
			return None
		src = src.split("?", 1)[0]
		if src.startswith("/private/files/"):
			# private files are permission-gated through the File doctype — the
			# browser path enforces this over HTTP, so the direct read must too
			file_names = frappe.get_all("File", filters={"file_url": src}, pluck="name")
			if not any(frappe.has_permission("File", doc=name, ptype="read") for name in file_names):
				return None
			root, rel = frappe.get_site_path("private", "files"), src[len("/private/files/") :]
		elif src.startswith("/files/"):
			root, rel = frappe.get_site_path("public", "files"), src[len("/files/") :]
		elif src.startswith("/assets/"):
			root, rel = frappe.get_site_path("..", "assets"), src[len("/assets/") :]
		else:
			return None
		# the src is document data — never let it walk out of its root
		root = os.path.realpath(root)
		path = os.path.realpath(os.path.join(root, rel))
		if not path.startswith(root + os.sep):
			return None
		try:
			# audited: realpath containment above, File permission for private paths
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
			with open(path, "rb") as f:
				return f.read()
		except OSError:
			return None

	@staticmethod
	def _dimension(width) -> str | None:
		if width in (None, ""):
			return None
		value = str(width).strip()
		if re.fullmatch(r"\d+(\.\d+)?(mm|cm|in|pt|%)", value):
			return value
		if value.endswith("px"):
			value = value[:-2]
		try:
			return f"{pt(value)}pt"
		except ValueError:
			return None

	def _embed_image(self, src) -> str | None:
		if not src:
			return None
		src = str(src)
		if src in self._embedded:
			return self._embedded[src]
		data = self._read_site_file(src)
		if data is None:
			name = None
		else:
			suffix = src.split("?", 1)[0].rsplit(".", 1)[-1].lower()
			if suffix not in ("png", "jpg", "jpeg", "svg", "gif", "webp"):
				suffix = "png"
			name = self._asset(suffix, data)
		self._embedded[src] = name
		return name

	def _image(self, df) -> str:
		src = df.get("image_url") or (self.doc.get(df.get("fieldname")) if df.get("fieldname") else "")
		if not src:
			return ""
		name = self._embed_image(src)
		if name is None:
			if df.get("image_url"):
				frappe.throw(
					_("The Typst renderer cannot embed this image: {0}").format(frappe.bold(str(src)[:100])),
					title=_("Typst renderer unavailable"),
				)
			# a document's own broken or remote image degrades to nothing,
			# like a dead <img> in the HTML render — it must not fail bulk email
			return ""
		width = self._dimension(df.get("width")) or "100%"
		return _aligned(f'#image("{name}", width: {width})', df.get("align"))

	def _barcode(self, df) -> str:
		data_uri = df.get("_qr_data_uri")
		if not data_uri:
			return ""
		data = self._read_site_file(data_uri)
		if data is None:
			return ""
		name = self._asset("svg", data)
		width = self._dimension(df.get("width")) or "35mm"
		return _aligned(f'#image("{name}", width: {width})', df.get("align"))

	def _repeater(self, df) -> str:
		source = df.get("source")
		rows = df.get("_rows") if df.get("_rows") is not None else (self.doc.get(source) if source else None)
		rows = rows or []
		columns = df.get("repeater_columns") or []
		if not rows or not columns:
			return ""

		widths = _fr_widths(columns)
		aligns = [
			col.get("align") if col.get("align") in ("left", "center", "right") else "left" for col in columns
		]
		fills = [
			f'fill: rgb("{color}"), ' if (color := safe_color(col.get("color"))) else "" for col in columns
		]

		cells = []
		for row in rows:
			for col, fill in zip(columns, fills, strict=True):
				parts = []
				for tok in col.get("template") or []:
					if not isinstance(tok, dict):
						continue
					if tok.get("t") == "f":
						parts.append(_text_value(row.get_formatted(tok.get("v"))))
					else:
						parts.append(str(tok.get("v") or ""))
				text = "".join(parts)
				cells.append(f"[#text({fill}{q(text)})]" if text else "[]")

		return (
			self._block_label(df)
			+ f"#table(columns: ({', '.join(widths)}), align: ({', '.join(aligns)},), stroke: none, inset: 4pt,\n"
			+ ",\n".join(cells)
			+ ")"
		)

	# ── tables ──────────────────────────────────────────────────

	def _table(self, df) -> str:
		columns = df.get("table_columns") or []
		if not columns:
			return ""
		rows = df.get("_rows") if df.get("_rows") is not None else self.doc.get(df.get("fieldname"))
		rows = rows or []
		if not rows:
			return ""

		widths = _fr_widths(columns)
		aligns = [
			"right" if (col.get("fieldtype") in RIGHT_ALIGNED_FIELDTYPES) else "left" for col in columns
		]

		header_cells = [
			f"#text(weight: 600, size: 0.85em, {q(_(col.get('label') or ''))})" for col in columns
		]
		body_cells = []
		for row in rows:
			for col in columns:
				body_cells.append(self._table_cell(row, col))

		# table_header is a mode string, not a flag: "none" drops the header, "plain"
		# keeps it without a fill (mirrors Table.html)
		header_mode = df.get("table_header")
		show_header = header_mode != "none"
		header_bg = None if header_mode == "plain" else safe_color(df.get("table_header_bg")) or "#f3f4f6"
		# full grid when explicitly bordered or table_style is bordered; otherwise
		# lined — horizontal rules between rows, matching the child-table classes
		if df.get("table_bordered") is not False or df.get("table_style") == "bordered":
			stroke = HAIRLINE
		else:
			stroke = f"(_, y) => if y > 0 {{ (top: {HAIRLINE}) }}"

		parts = [
			f"columns: ({', '.join(widths)})",
			f"align: ({', '.join(aligns)},)",
			f"stroke: {stroke}",
			f"inset: {pt(df.get('table_cell_padding'), 8)}pt",
		]
		if show_header:
			if header_bg:
				parts.append(f'fill: (_, row) => if row == 0 {{ rgb("{header_bg}") }}')
			cells = ["table.header(" + ", ".join(f"[{cell}]" for cell in header_cells) + ")"]
		else:
			cells = []
		cells += [f"[{cell}]" for cell in body_cells]
		return self._block_label(df) + "#table(" + ", ".join(parts) + ",\n" + ",\n".join(cells) + ")"

	def _block_label(self, df) -> str:
		if not df.get("label") or (df.get("show_label") or "show") == "hide":
			return ""
		return muted_text(_(df["label"]), self._label_color()) + "\n#v(3pt)\n"

	def _table_cell(self, row, col) -> str:
		merged = col.get("merged_fields")
		if merged:
			# the column's own field is the implicit primary line (Table.html:39)
			merged = [{"fieldname": col.get("fieldname"), "fieldtype": col.get("fieldtype")}, *merged]
			img_fn = next(
				(
					mf.get("fieldname")
					for mf in merged
					if mf.get("fieldname") and mf.get("fieldtype") in ("Attach Image", "Attach")
				),
				None,
			)
			lines = []
			first_text = True
			for mf in merged:
				fieldname = mf.get("fieldname")
				if not fieldname or mf.get("fieldtype") in ("Attach Image", "Attach"):
					continue
				value = _text_value(row.get_formatted(fieldname))
				if not value:
					continue
				if first_text:
					lines.append(f"#text(weight: 500, {q(value)})")
					first_text = False
				else:
					lines.append(muted_text(value))
			if not lines:
				body = ""
			elif len(lines) == 1:
				body = lines[0]
			elif col.get("merge_direction") == "horizontal":
				body = " #h(3pt) ".join(lines)
			else:
				body = "#stack(spacing: 3pt, " + ", ".join(f"[{line}]" for line in lines) + ")"
			if img_fn:
				thumb = self._table_thumb(row, col, img_fn, merged)
				if not body:
					return thumb
				return f"#grid(columns: (auto, 1fr), column-gutter: 6pt, align: top, [{thumb}], [{body}])"
			return body
		fieldname = col.get("fieldname")
		if not fieldname:
			return ""
		if fieldname == "idx":
			return f"#text({q(row.get('idx'))})"
		fieldtype = col.get("fieldtype")
		src = row.get(col.get("options") or "") if fieldtype == "Image" else row.get(fieldname)
		if fieldtype in ("Attach Image", "Image") or (
			fieldtype == "Attach" and frappe.utils.is_image(str(src or ""))
		):
			name = self._embed_image(src)
			if not name:
				return ""
			return f'#box(width: 100%, height: 75pt)[#image("{name}", width: 100%, height: 100%, fit: "contain")]'
		return f"#text({q(_text_value(row.get_formatted(fieldname)))})"

	def _table_thumb(self, row, col, img_fn, merged) -> str:
		size = pt(frappe.utils.cint(col.get("image_size")), 40)
		src = str(row.get(img_fn) or "")
		img_type = next((mf.get("fieldtype") for mf in merged if mf.get("fieldname") == img_fn), None)
		# a plain Attach can hold any file — embedding a PDF would abort the compile
		name = None
		if img_type != "Attach" or frappe.utils.is_image(src):
			name = self._embed_image(src)
		if name:
			return (
				f"#box(width: {size}pt, height: {size}pt, radius: 4.5pt, clip: true)"
				f'[#image("{name}", width: {size}pt, height: {size}pt, fit: "cover")]'
			)
		# no readable image: the coloured-initials fallback, same hue formula as
		# Table.html so all three surfaces show the same placeholder
		first_txt = next(
			(
				str(row.get(mf["fieldname"]) or "")
				for mf in merged
				if mf.get("fieldname") and mf["fieldname"] != img_fn
			),
			"",
		)
		abbr = frappe.utils.get_abbr(first_txt) or "?"
		idx = "abcdefghijklmnopqrstuvwxyz0123456789".find((abbr[:1] or "a").lower())
		hue = (max(idx, 0) * 37) % 360
		return (
			f"#box(width: {size}pt, height: {size}pt, radius: 4.5pt, fill: color.hsl({hue}deg, 65%, 92%))"
			f"[#align(center + horizon)[#text(size: {round(size * 0.4, 2)}pt, weight: 600, "
			f"fill: color.hsl({hue}deg, 55%, 35%), {q(abbr.upper())})]]"
		)
