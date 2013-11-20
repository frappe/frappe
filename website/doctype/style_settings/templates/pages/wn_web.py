# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
no_sitemap = True

def get_context():
	"""returns web style"""
	from webnotes.webutils import get_hex_shade
	
	doc = webnotes.doc("Style Settings", "Style Settings")
	prepare(doc)
	
	return {
		"doc": doc,
		"get_hex_shade": get_hex_shade
	}

def prepare(doc):
	from webnotes.utils import cint, cstr
	
	# set default colours
	default_colours = {
		"background_color": "FFFFFF",
		"page_background": "FFFFFF",
		"top_bar_background": "FFFFFF",
		"top_bar_foreground": "444444",
		"page_headings": "222222",
		"page_text": "000000"
	}
	
	for d in default_colours:
		if not doc.fields.get(d):
			doc.fields[d] = default_colours[d]
	
	if not doc.font_size:
		doc.font_size = "13px"
		
	doc.small_font_size = cstr(cint(doc.font_size[:-2])-2) + 'px'
	doc.page_border = cint(doc.page_border)
		
	fonts = []
	if doc.google_web_font_for_heading:
		fonts.append(doc.google_web_font_for_heading)
	if doc.google_web_font_for_text:
		fonts.append(doc.google_web_font_for_text)
		
	fonts = list(set(fonts))
	
	if doc.heading_text_as:
		doc.heading_text_style = {
			"UPPERCASE": "uppercase",
			"Title Case":"capitalize",
			"lowercase": "lowercase"
		}.get(doc.heading_text_as) or ""
	
	doc.at_import = ""
	for f in fonts:
		doc.at_import += "\n@import url(https://fonts.googleapis.com/css?family=%s:400,700);" % f.replace(" ", "+")
		
	# move @import from add_css field to the top of the css file
	if doc.add_css and "@import url" in doc.add_css:
		import re
		at_imports = list(set(re.findall("@import url\([^\(\)]*\);", doc.add_css)))
		doc.at_import += "\n" + "\n".join(at_imports)
		for imp in at_imports:
			doc.add_css = doc.add_css.replace(imp, "")