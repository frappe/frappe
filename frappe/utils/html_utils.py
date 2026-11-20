import json
import re

from bleach_allowlist import bleach_allowlist

import frappe
from frappe.utils.data import escape_html

EMOJI_PATTERN = re.compile(
	"(\ud83d[\ude00-\ude4f])|"
	"(\ud83c[\udf00-\uffff])|"
	"(\ud83d[\u0000-\uddff])|"
	"(\ud83d[\ude80-\udeff])|"
	"(\ud83c[\udde0-\uddff])"
	"+",
	flags=re.UNICODE,
)


def clean_html(html):
	import bleach

	if not isinstance(html, str):
		return html

	return bleach.clean(
		clean_script_and_style(html),
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
		attributes=[],
		strip=True,
		strip_comments=True,
	)


def clean_email_html(html):
	import bleach
	from bleach.css_sanitizer import CSSSanitizer

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

	return bleach.clean(
		clean_script_and_style(html),
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


def clean_script_and_style(html):
	# remove script and style
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(html, "html5lib")
	for s in soup(["script", "style"]):
		s.decompose()
	return frappe.as_unicode(soup)


def sanitize_html(html, linkify=False, always_sanitize=False, disallowed_tags=None):
	"""
	Sanitize HTML tags, attributes and style to prevent XSS attacks
	Based on bleach clean, bleach whitelist and html5lib's Sanitizer defaults

	Content without any HTML tags is returned unchanged; everything else is sanitized.
	"""
	import bleach
	from bleach.css_sanitizer import CSSSanitizer
	from bs4 import BeautifulSoup

	if not isinstance(html, str):
		return html

	if not always_sanitize:
		if not bool(BeautifulSoup(html, "html.parser").find()):
			return html

	tags = {
		*acceptable_elements,
		*svg_elements,
		*mathml_elements,
		"html",
		"head",
		"meta",
		"link",
		"body",
		"style",
		"o:p",
	}

	def attributes_filter(tag, name, value):
		if name.startswith("data-"):
			return True
		return name in acceptable_attributes

	attributes = {"*": attributes_filter, "svg": svg_attributes}
	css_sanitizer = CSSSanitizer(allowed_css_properties=bleach_allowlist.all_styles)

	# Allow caller to explicitly disallow some tags
	if disallowed_tags:
		if disallowed_tags == "*":
			tags = set()
		else:
			tags.difference_update(disallowed_tags)

	# returns html with escaped tags, escaped orphan >, <, etc.
	escaped_html = bleach.clean(
		html,
		tags=tags,
		attributes=attributes,
		css_sanitizer=css_sanitizer,
		strip_comments=False,
		protocols={"cid", "http", "https", "mailto"},
	)

	return escaped_html


# A request argument is a few levels deep at most: a document holding a child table
# of rows of fields is four. Past this the walk gives up and the text is sanitized
# as one blob, the way it was before it learned to look inside. A guest can post
# arbitrarily nested JSON, and walking it without a bound is a 500.
MAX_PAYLOAD_DEPTH = 20


class PayloadTooDeep(Exception):
	pass


def sanitize_html_payload(text):
	"""Sanitize HTML in a string that may be carrying a JSON payload.

	`sanitize_html` treats its input as a document that is itself HTML. A request
	argument is not that: anything richer than a scalar reaches `form_dict` as
	JSON, so the string is a container whose values may carry HTML.

	Sanitizing the serialized container rewrites the container. The parser reads
	an embedded tag such as `<div class=\\"x y\\">` (the backslashes are JSON
	escaping) as `class` holding the unquoted value `\\"x`, drops `y\\"` as a junk
	attribute, and writes the value back as `class="\\&quot;x"`. That bare quote
	ends the JSON string early and the payload no longer parses.

	So look inside instead. Decode, sanitize each string in the structure, and
	re-encode. A payload that needed no cleaning is returned exactly as it
	arrived, and anything that is not JSON is sanitized as before.

	The walk stops at `MAX_PAYLOAD_DEPTH` and falls back to sanitizing the text
	as one blob. The content is sanitized either way, and the walk cannot run the
	interpreter out of stack on a payload built to be deep.
	"""
	if not isinstance(text, str):
		return text

	return _sanitize_payload(text, MAX_PAYLOAD_DEPTH)


def _sanitize_payload(text, depth):
	try:
		payload = json.loads(text)
	except (ValueError, RecursionError):
		return sanitize_html(text)

	try:
		sanitized = _sanitize_json_strings(payload, depth)
	except PayloadTooDeep:
		return sanitize_html(text)

	if sanitized == payload:
		return text

	return json.dumps(sanitized)


def _sanitize_json_strings(value, depth):
	"""Sanitize every string inside a decoded JSON value, leaving its shape alone.

	Strings go back through `_sanitize_payload`, so a payload nested inside another
	payload is handled the same way.

	Keys are left as they are. They are looked up as argument and field names,
	never rendered, and rewriting one could collide with another key and drop a
	value.
	"""
	if depth <= 0:
		raise PayloadTooDeep

	if isinstance(value, str):
		return _sanitize_payload(value, depth - 1)

	if isinstance(value, dict):
		return {key: _sanitize_json_strings(item, depth - 1) for key, item in value.items()}

	if isinstance(value, list):
		return [_sanitize_json_strings(item, depth - 1) for item in value]

	return value


def is_json(text):
	try:
		json.loads(text)
	except ValueError:
		return False
	else:
		return True


def get_icon_html(icon, small=False):
	from frappe.utils import is_image

	icon = icon or ""

	if icon and EMOJI_PATTERN.match(icon):
		return f'<span class="text-muted">{icon}</span>'

	if is_image(icon):
		return (
			f"<img style='width: 16px; height: 16px;' src={escape_html(icon)!r}>"
			if small
			else f"<img src={escape_html(icon)!r}>"
		)
	else:
		return f"<i class={escape_html(icon)!r}></i>"


def unescape_html(value):
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
	"columnalign",
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
	"mathvariant",
	"maxsize",
	"minsize",
	"other",
	"rowalign",
	"rowalign",
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
