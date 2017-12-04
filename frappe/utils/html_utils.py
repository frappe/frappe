import json
import bleach, bleach_whitelist.bleach_whitelist as bleach_whitelist
from six import string_types

def clean_html(html):
	if not isinstance(html, string_types):
		return html

	return bleach.clean(html,
		tags=['div', 'p', 'br', 'ul', 'ol', 'li', 'b', 'i', 'em',
			'table', 'thead', 'tbody', 'td', 'tr'],
		attributes=[],
		styles=['color', 'border', 'border-color'],
		strip=True, strip_comments=True)

def sanitize_html(html, linkify=False):
	"""
	Sanitize HTML tags, attributes and style to prevent XSS attacks
	Based on bleach clean, bleach whitelist and HTML5lib's Sanitizer defaults

	Does not sanitize JSON, as it could lead to future problems
	"""
	if not isinstance(html, string_types):
		return html

	elif is_json(html):
		return html

	tags = (acceptable_elements + svg_elements + mathml_elements
		+ ["html", "head", "meta", "link", "body", "iframe", "style", "o:p"])
	attributes = {"*": acceptable_attributes, 'svg': svg_attributes}
	styles = bleach_whitelist.all_styles
	strip_comments = False

	# retuns html with escaped tags, escaped orphan >, <, etc.
	escaped_html = bleach.clean(html, tags=tags, attributes=attributes, styles=styles, strip_comments=strip_comments)

	if linkify:
		escaped_html = bleach.linkify(escaped_html, callbacks=[])

	return escaped_html

def is_json(text):
	try:
		json.loads(text)
	except ValueError:
		return False
	else:
		return True

# adapted from https://raw.githubusercontent.com/html5lib/html5lib-python/4aa79f113e7486c7ec5d15a6e1777bfe546d3259/html5lib/sanitizer.py
acceptable_elements = [
	'a', 'abbr', 'acronym', 'address', 'area',
	'article', 'aside', 'audio', 'b', 'big', 'blockquote', 'br', 'button',
	'canvas', 'caption', 'center', 'cite', 'code', 'col', 'colgroup',
	'command', 'datagrid', 'datalist', 'dd', 'del', 'details', 'dfn',
	'dialog', 'dir', 'div', 'dl', 'dt', 'em', 'event-source', 'fieldset',
	'figcaption', 'figure', 'footer', 'font', 'form', 'header', 'h1',
	'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'input', 'ins',
	'keygen', 'kbd', 'label', 'legend', 'li', 'm', 'map', 'menu', 'meter',
	'multicol', 'nav', 'nextid', 'ol', 'output', 'optgroup', 'option',
	'p', 'pre', 'progress', 'q', 's', 'samp', 'section', 'select',
	'small', 'sound', 'source', 'spacer', 'span', 'strike', 'strong',
	'sub', 'sup', 'table', 'tbody', 'td', 'textarea', 'time', 'tfoot',
	'th', 'thead', 'tr', 'tt', 'u', 'ul', 'var', 'video'
]

mathml_elements = [
	'maction', 'math', 'merror', 'mfrac', 'mi',
	'mmultiscripts', 'mn', 'mo', 'mover', 'mpadded', 'mphantom',
	'mprescripts', 'mroot', 'mrow', 'mspace', 'msqrt', 'mstyle', 'msub',
	'msubsup', 'msup', 'mtable', 'mtd', 'mtext', 'mtr', 'munder',
	'munderover', 'none'
]

svg_elements = [
	'a', 'animate', 'animateColor', 'animateMotion',
	'animateTransform', 'clipPath', 'circle', 'defs', 'desc', 'ellipse',
	'font-face', 'font-face-name', 'font-face-src', 'g', 'glyph', 'hkern',
	'linearGradient', 'line', 'marker', 'metadata', 'missing-glyph',
	'mpath', 'path', 'polygon', 'polyline', 'radialGradient', 'rect',
	'set', 'stop', 'svg', 'switch', 'text', 'title', 'tspan', 'use'
]

acceptable_attributes = [
	'abbr', 'accept', 'accept-charset', 'accesskey',
	'action', 'align', 'alt', 'autocomplete', 'autofocus', 'axis',
	'background', 'balance', 'bgcolor', 'bgproperties', 'border',
	'bordercolor', 'bordercolordark', 'bordercolorlight', 'bottompadding',
	'cellpadding', 'cellspacing', 'ch', 'challenge', 'char', 'charoff',
	'choff', 'charset', 'checked', 'cite', 'class', 'clear', 'color',
	'cols', 'colspan', 'compact', 'contenteditable', 'controls', 'coords',
	'data', 'datafld', 'datapagesize', 'datasrc', 'datetime', 'default',
	'delay', 'dir', 'disabled', 'draggable', 'dynsrc', 'enctype', 'end',
	'face', 'for', 'form', 'frame', 'galleryimg', 'gutter', 'headers',
	'height', 'hidefocus', 'hidden', 'high', 'href', 'hreflang', 'hspace',
	'icon', 'id', 'inputmode', 'ismap', 'keytype', 'label', 'leftspacing',
	'lang', 'list', 'longdesc', 'loop', 'loopcount', 'loopend',
	'loopstart', 'low', 'lowsrc', 'max', 'maxlength', 'media', 'method',
	'min', 'multiple', 'name', 'nohref', 'noshade', 'nowrap', 'open',
	'optimum', 'pattern', 'ping', 'point-size', 'poster', 'pqg', 'preload',
	'prompt', 'radiogroup', 'readonly', 'rel', 'repeat-max', 'repeat-min',
	'replace', 'required', 'rev', 'rightspacing', 'rows', 'rowspan',
	'rules', 'scope', 'selected', 'shape', 'size', 'span', 'src', 'start',
	'step', 'style', 'summary', 'suppress', 'tabindex', 'target',
	'template', 'title', 'toppadding', 'type', 'unselectable', 'usemap',
	'urn', 'valign', 'value', 'variable', 'volume', 'vspace', 'vrml',
	'width', 'wrap', 'xml:lang'
]

mathml_attributes = [
	'actiontype', 'align', 'columnalign', 'columnalign',
	'columnalign', 'columnlines', 'columnspacing', 'columnspan', 'depth',
	'display', 'displaystyle', 'equalcolumns', 'equalrows', 'fence',
	'fontstyle', 'fontweight', 'frame', 'height', 'linethickness', 'lspace',
	'mathbackground', 'mathcolor', 'mathvariant', 'mathvariant', 'maxsize',
	'minsize', 'other', 'rowalign', 'rowalign', 'rowalign', 'rowlines',
	'rowspacing', 'rowspan', 'rspace', 'scriptlevel', 'selection',
	'separator', 'stretchy', 'width', 'width', 'xlink:href', 'xlink:show',
	'xlink:type', 'xmlns', 'xmlns:xlink'
]

svg_attributes = [
	'accent-height', 'accumulate', 'additive', 'alphabetic',
	'arabic-form', 'ascent', 'attributeName', 'attributeType',
	'baseProfile', 'bbox', 'begin', 'by', 'calcMode', 'cap-height',
	'class', 'clip-path', 'color', 'color-rendering', 'content', 'cx',
	'cy', 'd', 'dx', 'dy', 'descent', 'display', 'dur', 'end', 'fill',
	'fill-opacity', 'fill-rule', 'font-family', 'font-size',
	'font-stretch', 'font-style', 'font-variant', 'font-weight', 'from',
	'fx', 'fy', 'g1', 'g2', 'glyph-name', 'gradientUnits', 'hanging',
	'height', 'horiz-adv-x', 'horiz-origin-x', 'id', 'ideographic', 'k',
	'keyPoints', 'keySplines', 'keyTimes', 'lang', 'marker-end',
	'marker-mid', 'marker-start', 'markerHeight', 'markerUnits',
	'markerWidth', 'mathematical', 'max', 'min', 'name', 'offset',
	'opacity', 'orient', 'origin', 'overline-position',
	'overline-thickness', 'panose-1', 'path', 'pathLength', 'points',
	'preserveAspectRatio', 'r', 'refX', 'refY', 'repeatCount',
	'repeatDur', 'requiredExtensions', 'requiredFeatures', 'restart',
	'rotate', 'rx', 'ry', 'slope', 'stemh', 'stemv', 'stop-color',
	'stop-opacity', 'strikethrough-position', 'strikethrough-thickness',
	'stroke', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap',
	'stroke-linejoin', 'stroke-miterlimit', 'stroke-opacity',
	'stroke-width', 'systemLanguage', 'target', 'text-anchor', 'to',
	'transform', 'type', 'u1', 'u2', 'underline-position',
	'underline-thickness', 'unicode', 'unicode-range', 'units-per-em',
	'values', 'version', 'viewBox', 'visibility', 'width', 'widths', 'x',
	'x-height', 'x1', 'x2', 'xlink:actuate', 'xlink:arcrole',
	'xlink:href', 'xlink:role', 'xlink:show', 'xlink:title', 'xlink:type',
	'xml:base', 'xml:lang', 'xml:space', 'xmlns', 'xmlns:xlink', 'y',
	'y1', 'y2', 'zoomAndPan'
]