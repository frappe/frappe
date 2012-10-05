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

def read_csv_content_from_uploaded_file():
	from webnotes.utils.file_manager import get_uploaded_content
	fname, fcontent = get_uploaded_content()
	return read_csv_content(fcontent)

def read_csv_content_from_attached_file(doc):
	if not doc.file_list:
		msgprint("File not attached!")
		raise Exception

	try:
		from webnotes.utils.file_manager import get_file
		fid = doc.file_list.split(",")[1]
		fname, fcontent = get_file(fid)
		return read_csv_content(fcontent)
	except Exception, e:
		webnotes.msgprint("""Unable to open attached file. Please try again.""")
		raise Exception

def read_csv_content(fcontent):
	import csv
	from webnotes.utils import cstr
	rows = []
	try:
		reader = csv.reader(fcontent.splitlines())
		# decode everything
		csvrows = [[val for val in row] for row in reader]
		
		for row in csvrows:
			newrow = []
			for val in row:
				if webnotes.form_dict.get('ignore_encoding_errors'):
					newrow.append(cstr(val.strip()))
				else:
					try:
						newrow.append(unicode(val.strip(), 'utf-8'))
					except UnicodeDecodeError, e:
						raise Exception, """Some character(s) in row #%s, column #%s are
							not readable by utf-8. Ignoring them. If you are importing a non
							english language, please make sure your file is saved in the 'utf-8'
							encoding.""" % (csvrows.index(row)+1, row.index(val)+1)
					
			rows.append(newrow)
		
		return rows
	except Exception, e:
		webnotes.msgprint("Not a valid Comma Separated Value (CSV File)")
		raise e