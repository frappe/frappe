import json
import re

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bleach_allowlist import bleach_allowlist
from bs4 import BeautifulSoup, Comment, NavigableString

import frappe
from frappe.utils.data import escape_html

EMOJI_PATTERN = re.compile(
	r"(\ud83d[\ude00-\ude4f])|"
	r"(\ud83c[\udf00-\uffff])|"
	r"(\ud83d[\u0000-\uddff])|"
	r"(\ud83d[\ude80-\udeff])|"
	r"(\ud83c[\udde0-\uddff])+",
	flags=re.UNICODE,
)


def clean_html(html):
	"""
	Light-weight HTML sanitization for user-generated fragments:
	strips scripts/styles, allows a small set of tags, removes comments.
	"""
	if not isinstance(html, str):
		return html

	fragment = clean_script_and_style(html)
	return bleach.clean(
		fragment,
		tags={
			"div",
			"p",
			"br",
			"ul",
			"ol",
			"li",
			"strong",
			"b",
			"em",
			"i",
			"u",
			"table",
			"thead",
			"tbody",
			"td",
			"tr",
		},
		attributes={},
		strip=True,
		strip_comments=True,
	)


def clean_email_html(html):
	"""
	Email-safe HTML sanitization:
	strips scripts/styles, allows common email tags + inline CSS properties.
	"""
	if not isinstance(html, str):
		return html

	css_sanitizer = CSSSanitizer(
		allowed_css_properties=[
			"color",
			"border-color",
			"width",
			"height",
			"max-width",
			"background-color",
			"border-collapse",
			"border-radius",
			"border",
			"border-top",
			"border-bottom",
			"border-left",
			"border-right",
			"margin",
			"margin-top",
			"margin-bottom",
			"margin-left",
			"margin-right",
			"padding",
			"padding-top",
			"padding-bottom",
			"padding-left",
			"padding-right",
			"font-size",
			"font-weight",
			"font-family",
			"text-decoration",
			"line-height",
			"text-align",
			"vertical-align",
			"display",
		]
	)

	fragment = clean_script_and_style(html)
	return bleach.clean(
		fragment,
		tags={
			"div",
			"p",
			"br",
			"ul",
			"ol",
			"li",
			"strong",
			"b",
			"em",
			"i",
			"u",
			"a",
			"table",
			"thead",
			"tbody",
			"td",
			"tr",
			"th",
			"pre",
			"code",
			"h1",
			"h2",
			"h3",
			"h4",
			"h5",
			"h6",
			"button",
			"img",
		},
		attributes=["border", "colspan", "rowspan", "src", "href", "style", "id"],
		css_sanitizer=css_sanitizer,
		protocols=["cid", "http", "https", "mailto", "data"],
		strip=True,
		strip_comments=True,
	)


def clean_script_and_style(html: str, features="html5lib") -> str:
	"""
	Remove all <script> and <style> tags via html5lib parsing by default.
	Preserves other tags and text exactly.
	"""
	soup = BeautifulSoup(html, features)
	for tag in soup(["script", "style"]):
		tag.decompose()
	return frappe.as_unicode(soup)


def clean_script(html: str, features="html5lib") -> str:
	"""
	Remove all <script> tags via html5lib parsing by default.
	Preserves other tags and text exactly.
	"""
	soup = BeautifulSoup(html, features)
	for tag in soup(["script"]):
		tag.decompose()
	return frappe.as_unicode(soup)


def sanitize_html(html, linkify=False, always_sanitize=False):
	"""
	Comprehensive HTML sanitization for DB storage:

	1) Full documents (<!DOCTYPE> or <html>): strip <script>, remove comments,
	   preserve <head>, <style>, entities; re-serialize with entities intact.
	2) Plain text or JSON: returned unchanged (unless always_sanitize=True).
	3) HTML fragments: bleach.clean → optional linkify → remove comments →
	   re-serialize with entities intact.
	"""
	if not isinstance(html, str):
		return html

	stripped = html.lstrip().lower()

	# --- 1) FULL DOCUMENT FLOW ---
	if (
		stripped.startswith("<!doctype")
		or stripped.startswith("<html")
		or (len(html.splitlines()) > 1 and html.splitlines()[1].strip().lower().startswith("<!doctype"))
	):
		# parse with html5lib for spec-correct DOM
		soup = BeautifulSoup(html, "html5lib")

		# remove <script>
		for tag in soup(["script"]):
			tag.decompose()

		# strip HTML comments
		for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
			comment.extract()

		# remove pure-whitespace text nodes at top level
		for text_node in soup.find_all(string=lambda t: isinstance(t, NavigableString) and not t.strip()):
			text_node.extract()

		# serialize with entities intact
		return soup.decode(formatter="html5")

	# --- 2) SHORT-CIRCUIT: JSON or no tags ---
	if not always_sanitize:
		try:
			json.loads(html)
			return html
		except ValueError:
			pass

		# if no tags at all, leave untouched
		if not BeautifulSoup(html, "html.parser").find():
			return html

	# Strip script tags
	html = clean_script_and_style(html, features="html.parser")

	# --- 3) FRAGMENT SANITIZATION FLOW ---
	allowed_tags = set(acceptable_elements) | set(svg_elements) | set(mathml_elements)
	allowed_tags |= {"html", "head", "meta", "link", "body", "style", "o:p"}

	def _attr_filter(tag, name, value):
		nl = name.lower()
		# disallow JS events
		if nl.startswith("on"):
			return False
		# allow data-* and xmlns-*
		if nl.startswith("data-") or nl.startswith("xmlns"):
			return True
		# allow explicitly allowed attributes
		if nl in acceptable_attributes or nl in {"http-equiv", "emogrify"}:
			return True
		return False

	attributes = {"*": _attr_filter, "svg": svg_attributes}

	css_sanitizer = CSSSanitizer(allowed_css_properties=bleach_allowlist.all_styles)

	cleaned = bleach.clean(
		html,
		tags=allowed_tags,
		attributes=attributes,
		css_sanitizer=css_sanitizer,
		protocols={"cid", "http", "https", "mailto", "data"},
		strip=True,
		strip_comments=True,
	)

	if linkify:
		cleaned = bleach.linkify(cleaned)

	# re-parse fragments with fast html.parser
	fragment = BeautifulSoup(cleaned, "html.parser")
	output_parts = []

	for node in fragment.contents:
		if isinstance(node, NavigableString):
			text = str(node)
			# skip if it`s just spaces/newlines
			if not text.strip():
				continue
			output_parts.append(text.strip())
		else:
			# for each element, strip comments under it then re-serialize
			for comment in node.find_all(string=lambda t: isinstance(t, Comment)):
				comment.extract()
			# use minimal escaping for readability
			output_parts.append(node.decode(formatter="minimal"))

	return "".join(output_parts)


def is_json(text):
	"""Return True if text is valid JSON."""
	try:
		json.loads(text)
	except ValueError:
		return False
	return True


def get_icon_html(icon, small=False):
	"""
	Return HTML for emoji, image or <i> tag, safe-escaped.
	"""
	from frappe.utils import is_image

	icon = icon or ""
	if icon and EMOJI_PATTERN.match(icon):
		return f'<span class="text-muted">{icon}</span>'

	if is_image(icon):
		tag = f"<img src={escape_html(icon)!r}"
		if small:
			tag += " style='width:16px;height:16px;'"
		tag += ">"
		return tag

	return f"<i class={escape_html(icon)!r}></i>"


def unescape_html(value):
	"""Convert HTML entities back to unicode characters."""
	from html import unescape

	return unescape(value)


# adapted from https://raw.githubusercontent.com/html5lib/html5lib-python/4aa79f113e7486c7ec5d15a6e1777bfe546d3259/html5lib/sanitizer.py

acceptable_elements = [
	"a",
	"abbr",
	"acronym",
	"address",
	"area",
	"article",
	"aside",
	"audio",
	"b",
	"big",
	"blockquote",
	"br",
	"button",
	"canvas",
	"caption",
	"center",
	"cite",
	"code",
	"col",
	"colgroup",
	"command",
	"datagrid",
	"datalist",
	"dd",
	"del",
	"details",
	"dfn",
	"dialog",
	"dir",
	"div",
	"dl",
	"dt",
	"em",
	"event-source",
	"fieldset",
	"figcaption",
	"figure",
	"footer",
	"font",
	"form",
	"header",
	"h1",
	"h2",
	"h3",
	"h4",
	"h5",
	"h6",
	"hr",
	"i",
	"img",
	"input",
	"ins",
	"keygen",
	"kbd",
	"label",
	"legend",
	"li",
	"m",
	"map",
	"mark",
	"menu",
	"meter",
	"multicol",
	"nav",
	"nextid",
	"ol",
	"output",
	"optgroup",
	"option",
	"p",
	"pre",
	"progress",
	"q",
	"s",
	"samp",
	"section",
	"select",
	"small",
	"sound",
	"source",
	"spacer",
	"span",
	"strike",
	"strong",
	"sub",
	"summary",
	"sup",
	"table",
	"tbody",
	"td",
	"textarea",
	"time",
	"tfoot",
	"th",
	"thead",
	"tr",
	"tt",
	"u",
	"ul",
	"var",
	"video",
]

mathml_elements = [
	"maction",
	"math",
	"merror",
	"mfrac",
	"mi",
	"mmultiscripts",
	"mn",
	"mo",
	"mover",
	"mpadded",
	"mphantom",
	"mprescripts",
	"mroot",
	"mrow",
	"mspace",
	"msqrt",
	"mstyle",
	"msub",
	"msubsup",
	"msup",
	"mtable",
	"mtd",
	"mtext",
	"mtr",
	"munder",
	"munderover",
	"none",
]

svg_elements = [
	"a",
	"animate",
	"animateColor",
	"animateMotion",
	"animateTransform",
	"clipPath",
	"circle",
	"defs",
	"desc",
	"ellipse",
	"font-face",
	"font-face-name",
	"font-face-src",
	"g",
	"glyph",
	"hkern",
	"linearGradient",
	"line",
	"marker",
	"metadata",
	"missing-glyph",
	"mpath",
	"path",
	"polygon",
	"polyline",
	"radialGradient",
	"rect",
	"set",
	"stop",
	"svg",
	"switch",
	"text",
	"title",
	"tspan",
	"use",
]

acceptable_attributes = [
	"abbr",
	"accept",
	"accept-charset",
	"accesskey",
	"action",
	"align",
	"alt",
	"autocomplete",
	"autofocus",
	"axis",
	"background",
	"balance",
	"bgcolor",
	"bgproperties",
	"border",
	"bordercolor",
	"bordercolordark",
	"bordercolorlight",
	"bottompadding",
	"cellpadding",
	"cellspacing",
	"ch",
	"challenge",
	"char",
	"charoff",
	"choff",
	"charset",
	"checked",
	"cite",
	"class",
	"clear",
	"color",
	"cols",
	"colspan",
	"compact",
	"content",
	"contenteditable",
	"controls",
	"coords",
	"data",
	"datafld",
	"datapagesize",
	"datasrc",
	"datetime",
	"default",
	"delay",
	"dir",
	"disabled",
	"draggable",
	"dynsrc",
	"enctype",
	"end",
	"face",
	"for",
	"form",
	"frame",
	"galleryimg",
	"gutter",
	"headers",
	"height",
	"hidefocus",
	"hidden",
	"high",
	"href",
	"hreflang",
	"hspace",
	"icon",
	"id",
	"inputmode",
	"ismap",
	"keytype",
	"label",
	"leftspacing",
	"lang",
	"list",
	"longdesc",
	"loop",
	"loopcount",
	"loopend",
	"loopstart",
	"low",
	"lowsrc",
	"max",
	"maxlength",
	"media",
	"method",
	"min",
	"multiple",
	"name",
	"nohref",
	"noshade",
	"nowrap",
	"open",
	"optimum",
	"pattern",
	"ping",
	"point-size",
	"poster",
	"pqg",
	"preload",
	"prompt",
	"radiogroup",
	"readonly",
	"rel",
	"repeat-max",
	"repeat-min",
	"replace",
	"required",
	"rev",
	"rightspacing",
	"rows",
	"rowspan",
	"rules",
	"scope",
	"selected",
	"shape",
	"size",
	"span",
	"src",
	"start",
	"step",
	"style",
	"summary",
	"suppress",
	"tabindex",
	"target",
	"template",
	"title",
	"toppadding",
	"type",
	"unselectable",
	"usemap",
	"urn",
	"valign",
	"value",
	"variable",
	"volume",
	"vspace",
	"vrml",
	"width",
	"wrap",
	"xml:lang",
	"data-row",
	"data-list",
	"data-language",
	"data-value",
	"role",
	"frameborder",
	"allowfullscreen",
	"spellcheck",
	"data-mode",
	"data-gramm",
	"data-placeholder",
	"data-comment",
	"data-id",
	"data-denotation-char",
	"itemprop",
	"itemscope",
	"itemtype",
	"itemid",
	"itemref",
	"datetime",
	"data-is-group",
]

mathml_attributes = [
	"actiontype",
	"align",
	"columnalign",
	"columnlines",
	"columnspacing",
	"columnspan",
	"depth",
	"display",
	"displaystyle",
	"equalcolumns",
	"equalrows",
	"fence",
	"fontstyle",
	"fontweight",
	"frame",
	"height",
	"linethickness",
	"lspace",
	"mathbackground",
	"mathcolor",
	"mathvariant",
	"maxsize",
	"minsize",
	"other",
	"rowalign",
	"rowlines",
	"rowspacing",
	"rowspan",
	"rspace",
	"scriptlevel",
	"selection",
	"separator",
	"stretchy",
	"width",
	"xlink:href",
	"xlink:show",
	"xlink:type",
	"xmlns",
	"xmlns:xlink",
]

svg_attributes = [
	"accent-height",
	"accumulate",
	"additive",
	"alphabetic",
	"arabic-form",
	"ascent",
	"attributeName",
	"attributeType",
	"baseProfile",
	"bbox",
	"begin",
	"by",
	"calcMode",
	"cap-height",
	"class",
	"clip-path",
	"color",
	"color-rendering",
	"content",
	"colwidth",
	"cx",
	"cy",
	"d",
	"dx",
	"dy",
	"descent",
	"display",
	"dur",
	"end",
	"fill",
	"fill-opacity",
	"fill-rule",
	"font-family",
	"font-size",
	"font-stretch",
	"font-style",
	"font-variant",
	"font-weight",
	"from",
	"fx",
	"fy",
	"g1",
	"g2",
	"glyph-name",
	"gradientUnits",
	"hanging",
	"height",
	"horiz-adv-x",
	"horiz-origin-x",
	"id",
	"ideographic",
	"k",
	"keyPoints",
	"keySplines",
	"keyTimes",
	"lang",
	"marker-end",
	"marker-mid",
	"marker-start",
	"markerHeight",
	"markerUnits",
	"markerWidth",
	"mathematical",
	"max",
	"min",
	"name",
	"offset",
	"opacity",
	"orient",
	"origin",
	"overline-position",
	"overline-thickness",
	"panose-1",
	"path",
	"pathLength",
	"points",
	"preserveAspectRatio",
	"r",
	"refX",
	"refY",
	"repeatCount",
	"repeatDur",
	"requiredExtensions",
	"requiredFeatures",
	"restart",
	"rotate",
	"rx",
	"ry",
	"slope",
	"stemh",
	"stemv",
	"stop-color",
	"stop-opacity",
	"strikethrough-position",
	"strikethrough-thickness",
	"stroke",
	"stroke-dasharray",
	"stroke-dashoffset",
	"stroke-linecap",
	"stroke-linejoin",
	"stroke-miterlimit",
	"stroke-opacity",
	"stroke-width",
	"systemLanguage",
	"target",
	"text-anchor",
	"to",
	"transform",
	"type",
	"u1",
	"u2",
	"underline-position",
	"underline-thickness",
	"unicode",
	"unicode-range",
	"units-per-em",
	"values",
	"version",
	"viewBox",
	"visibility",
	"width",
	"widths",
	"x",
	"x-height",
	"x1",
	"x2",
	"xlink:actuate",
	"xlink:arcrole",
	"xlink:href",
	"xlink:role",
	"xlink:show",
	"xlink:title",
	"xlink:type",
	"xml:base",
	"xml:lang",
	"xml:space",
	"xmlns",
	"xmlns:xlink",
	"y",
	"y1",
	"y2",
	"zoomAndPan",
]
