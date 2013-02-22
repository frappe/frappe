# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import unicode_literals
import webnotes

from webnotes import _

@webnotes.whitelist()
def run(report_name):
	report = webnotes.doc("Report", report_name)

	if not webnotes.has_permission(report.ref_doctype, "report"):
		webnotes.msgprint(_("Must have report permission to access this report."), 
			raise_exception=True)
	
	if report.report_type=="Query Report":
		if not report.query:
			webnotes.msgprint(_("Must specify a Query to run"), raise_exception=True)
	
	
		if not report.query.lower().startswith("select"):
			webnotes.msgprint(_("Query must be a SELECT"), raise_exception=True)
		
		result = [list(t) for t in webnotes.conn.sql(report.query)]
		columns = [c[0] for c in webnotes.conn.get_description()]
	else:
		from webnotes.modules import scrub
		method_name = scrub(webnotes.conn.get_value("DocType", report.ref_doctype, "module")) \
			+ ".report." + scrub(report.name) + "." + scrub(report.name) + ".execute"
		columns, result = webnotes.get_method(method_name)()
	
	return {
		"result": result,
		"columns": columns
	}