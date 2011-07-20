in_files_main = [
	'utils/rsh.compressed.js'
	,'globals.js'
	,'utils/datatype.js'
	,'utils/browser_detect.js'
	,'utils/datetime.js'
	,'utils/dom.js'
	,'utils/handler.js'
	,'utils/msgprint.js'
	,'utils/json.js'
	,'utils/shortcut.js'
	,'utils/printElement.js'
	,'wn/widgets/dialog.js'
	,'widgets/dialog.js'
	,'widgets/listing.js'
	,'wn/widgets/listing.js'
	,'widgets/tree.js'
	,'widgets/menu.js'
	,'widgets/layout.js'
	,'widgets/tabbedpage.js'
	,'webpage/page_header.js'
	,'widgets/autosuggest.js'
	,'widgets/select.js'
	,'widgets/tags.js'
	,'widgets/export_query.js'
	,'widgets/list_selector.js'
	,'widgets/form/fields.js'
	,'webpage/wntoolbar.js'
	,'webpage/history.js'
	,'webpage/search.js'
	,'webpage/spinner.js'
	,'webpage/freeze_page.js'
	,'webpage/error_console.js'
	,'webpage/about.js'
	,'webpage/loaders.js'
	,'webpage/uploader.js'
	,'webpage/page.js'
	,'webpage/docbrowser.js'
	,'wn/page_layout.js'
	#,'wn/widgets/doc_column_view.js'
	,'wn/widgets/page_sidebar.js'
	,'wn/widgets/footer.js'
	#,'wn/widgets/follow.js'
	,'model/local_data.js'
	,'model/doclist.js'
	,'webpage/body.js'
	,'app.js'
	,'widgets/calendar.js'
	 ]

out_file_main = 'js/wnf.compressed.js'

#-------------------------------------------------

in_files_lite = [
	'utils/rsh.compressed.js'
	,'globals.js'
	,'utils/datatype.js'
	,'utils/browser_detect.js'
	,'utils/datetime.js'
	,'utils/dom.js'
	,'utils/handler.js'
	,'utils/msgprint.js'
	,'utils/json.js'
	,'wn/widgets/dialog.js'
	,'widgets/dialog.js'
	,'widgets/listing.js'
	,'widgets/layout.js'
	,'widgets/tabbedpage.js'
	,'webpage/page_header.js'
	,'widgets/autosuggest.js'
	,'widgets/tags.js'
	,'widgets/form/fields.js'
	,'webpage/history.js'
	,'webpage/search.js'
	,'webpage/spinner.js'
	,'webpage/freeze_page.js'
	,'webpage/error_console.js'
	,'webpage/about.js'
	,'webpage/loaders.js'
	,'webpage/uploader.js'
	,'webpage/page.js'
	,'wn/widgets/page_sidebar.js'
	,'wn/widgets/follow.js'
	,'model/local_data.js'
	,'model/doclist.js'
	,'webpage/body.js'
	,'app.js'
	 ]

out_file_lite = 'js/wnf-lite.compressed.js'

#-------------------------------------------------

in_files_form = [
	 'widgets/form/form_container.js'
	,'widgets/form/form_header.js'
	,'widgets/form/form.js'
	,'widgets/form/form_fields.js'
	,'widgets/form/grid.js'
	,'widgets/form/form_grid.js'
	,'widgets/form/print_format.js'
	,'widgets/form/email.js'
	,'widgets/form/clientscriptAPI.js'
	,'widgets/form/form_comments.js'
	,'wn/widgets/form/sidebar.js'
	,'wn/widgets/form/comments.js'
	,'wn/widgets/form/attachments.js'
]

out_file_form = 'js/form.compressed.js';

in_files_report = [
	'widgets/report_builder/bargraph.js'
	,'widgets/report_builder/report_builder.js'
	,'widgets/report_builder/datatable.js'
	,'widgets/report_builder/calculator.js'
]

out_file_report = 'js/report.compressed.js'

in_files_css = [
	'css/body.css',
	'css/menus.css',
	'css/messages.css',
	'css/forms.css',
	'css/grid.css',
	'css/listing.css',
	'css/report.css',
	'css/calendar.css',
	'css/autosuggest.css',
	'css/dialog.css',
	'css/wntoolbar.css',
	'css/tabs.css',
	'css/jqplot.css',
	'css/bw-icons.css',
	'css/sidebar.css',
	'css/doc_column_view.css',
]

out_file_css = 'css/default.css'



#in_files_main += in_files_form

import os, os.path, shutil

# This code is original from jsmin by Douglas Crockford, it was translated to
# Python by Baruch Even. The original code had the following copyright and
# license.
#
# /* jsmin.c
#	2007-05-22
#
# Copyright (c) 2002 Douglas Crockford  (www.crockford.com)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# The Software shall be used for Good, not Evil.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# */

from StringIO import StringIO

def jsmin(js):
	ins = StringIO(js)
	outs = StringIO()
	JavascriptMinify().minify(ins, outs)
	str = outs.getvalue()
	if len(str) > 0 and str[0] == '\n':
		str = str[1:]
	return str

def isAlphanum(c):
	"""return true if the character is a letter, digit, underscore,
		   dollar sign, or non-ASCII character.
	"""
	return ((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9') or
			(c >= 'A' and c <= 'Z') or c == '_' or c == '$' or c == '\\' or (c is not None and ord(c) > 126));

class UnterminatedComment(Exception):
	pass

class UnterminatedStringLiteral(Exception):
	pass

class UnterminatedRegularExpression(Exception):
	pass

class JavascriptMinify(object):

	def _outA(self):
		self.outstream.write(self.theA)
	def _outB(self):
		self.outstream.write(self.theB)

	def _get(self):
		"""return the next character from stdin. Watch out for lookahead. If
		   the character is a control character, translate it to a space or
		   linefeed.
		"""
		c = self.theLookahead
		self.theLookahead = None
		if c == None:
			c = self.instream.read(1)
		if c >= ' ' or c == '\n':
			return c
		if c == '': # EOF
			return '\000'
		if c == '\r':
			return '\n'
		return ' '

	def _peek(self):
		self.theLookahead = self._get()
		return self.theLookahead

	def _next(self):
		"""get the next character, excluding comments. peek() is used to see
		   if an unescaped '/' is followed by a '/' or '*'.
		"""
		c = self._get()
		if c == '/' and self.theA != '\\':
			p = self._peek()
			if p == '/':
				c = self._get()
				while c > '\n':
					c = self._get()
				return c
			if p == '*':
				c = self._get()
				while 1:
					c = self._get()
					if c == '*':
						if self._peek() == '/':
							self._get()
							return ' '
					if c == '\000':
						raise UnterminatedComment()

		return c

	def _action(self, action):
		"""do something! What you do is determined by the argument:
		   1   Output A. Copy B to A. Get the next B.
		   2   Copy B to A. Get the next B. (Delete A).
		   3   Get the next B. (Delete B).
		   action treats a string as a single character. Wow!
		   action recognizes a regular expression if it is preceded by ( or , or =.
		"""
		if action <= 1:
			self._outA()

		if action <= 2:
			self.theA = self.theB
			if self.theA == "'" or self.theA == '"':
				while 1:
					self._outA()
					self.theA = self._get()
					if self.theA == self.theB:
						break
					if self.theA <= '\n':
						raise UnterminatedStringLiteral()
					if self.theA == '\\':
						self._outA()
						self.theA = self._get()


		if action <= 3:
			self.theB = self._next()
			if self.theB == '/' and (self.theA == '(' or self.theA == ',' or
									 self.theA == '=' or self.theA == ':' or
									 self.theA == '[' or self.theA == '?' or
									 self.theA == '!' or self.theA == '&' or
									 self.theA == '|' or self.theA == ';' or
									 self.theA == '{' or self.theA == '}' or
									 self.theA == '\n'):
				self._outA()
				self._outB()
				while 1:
					self.theA = self._get()
					if self.theA == '/':
						break
					elif self.theA == '\\':
						self._outA()
						self.theA = self._get()
					elif self.theA <= '\n':
						raise UnterminatedRegularExpression()
					self._outA()
				self.theB = self._next()


	def _jsmin(self):
		"""Copy the input to the output, deleting the characters which are
		   insignificant to JavaScript. Comments will be removed. Tabs will be
		   replaced with spaces. Carriage returns will be replaced with linefeeds.
		   Most spaces and linefeeds will be removed.
		"""
		self.theA = '\n'
		self._action(3)

		while self.theA != '\000':
			if self.theA == ' ':
				if isAlphanum(self.theB):
					self._action(1)
				else:
					self._action(2)
			elif self.theA == '\n':
				if self.theB in ['{', '[', '(', '+', '-']:
					self._action(1)
				elif self.theB == ' ':
					self._action(3)
				else:
					if isAlphanum(self.theB):
						self._action(1)
					else:
						self._action(2)
			else:
				if self.theB == ' ':
					if isAlphanum(self.theA):
						self._action(1)
					else:
						self._action(3)
				elif self.theB == '\n':
					if self.theA in ['}', ']', ')', '+', '-', '"', '\'']:
						self._action(1)
					else:
						if isAlphanum(self.theA):
							self._action(1)
						else:
							self._action(3)
				else:
					self._action(1)

	def minify(self, instream, outstream):
		self.instream = instream
		self.outstream = outstream
		self.theA = '\n'
		self.theB = None
		self.theLookahead = None

		self._jsmin()
		self.instream.close()

def combine_css():
	global out_file_css, in_files_css
	
	data = ''
	for f in in_files_css:
		fh = open(f, 'read')
		data += fh.read() + '\n'
		fh.close()
		
	out_file = open(out_file_css, 'w')
	out_file.write(data)
	out_file.close()

def _compress(in_files, out_file, in_type='js', verbose=False,
			 temp_file='.temp'):
	
	import os

	temp = open(temp_file, 'w')
	for f in in_files:
		print f + ' | ' + str(int(os.path.getsize('js/'+f)/1024)) + 'k'

		fh = open('js/' + f)
		data = fh.read() + '\n'
		fh.close()

		temp.write(data)

		#print ' + %s' % f
	temp.close()
	
	out = open(out_file, 'w')

	jsm = JavascriptMinify()
	jsm.minify(open(temp_file,'r'), out)

	out.close()

	org_size = os.path.getsize(temp_file)
	new_size = os.path.getsize(out_file)

	print '=> %s' % out_file
	print 'Original: %.2f kB' % (org_size / 1024.0)
	print 'Compressed: %.2f kB' % (new_size / 1024.0)
	print 'Reduction: %.1f%%' % (float(org_size - new_size) / org_size * 100)
	print ''

	os.remove(temp_file)

	
if __name__=='__main__':
	import sys
	if sys.argv[1]=='main':
		_compress(in_files_main, out_file_main)
	elif sys.argv[1]=='lite':
		_compress(in_files_lite, out_file_lite)
	elif sys.argv[1]=='form':
		_compress(in_files_form, out_file_form)
	elif sys.argv[1]=='report':
		_compress(in_files_report, out_file_report)
	elif sys.argv[1]=='css':
		combine_css()
	else:
		print 'parameter must be one of main, lite, css, form or report'	
		
