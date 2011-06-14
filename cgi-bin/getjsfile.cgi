#!/usr/bin/python

import cgi
import datetime
import os

try:

	form = cgi.FieldStorage()
	out = ''
	out_buf, str_out = '', ''
	jsdir='../js'
	jsonout= {}

	# Traceback
	# ---------
	def getTraceback():
		import sys, traceback, string
		type, value, tb = sys.exc_info()
		body = "Traceback (innermost last):\n"
		list = traceback.format_tb(tb, None) \
			+ traceback.format_exception_only(type, value)
		body = body + "%-20s %s" % (string.join(list[:-1], ""), list[-1])
		return body
		
	def load_js_from_file(module_name):
		global out
		global jsonout
		import webnotes.utils.jsnamespace as jsn
		filename = jsn.jsNamespace.modname_to_filename(module_name,jsdir)
		import os
		try:
			f = open(os.path.join(filename))
			try:
				out = f.read()
			finally:
				f.close()
		except IOError,e:
			out = "Not Found: %s" % filename
		jsonout[module_name]=out
	
	def load_js_module(module_name):
		global jsonout
		from webnotes import defs
		devmode = getattr(defs,'developer_mode')
		if devmode:
			import compilejs
			compilejs.wnJSCompiler.compilejs(jsdir)
		if module_name not in jsonout:
			dependent_mods = get_dependencies(module_name)
			for module in dependent_mods:
				load_js_from_file(module)
		load_js_from_file(module_name)
	
	def get_dependencies(module_name):
		import webnotes.utils.jsdependency as jsd
		ret = jsd.jsDependencyBuilder.build_dependency(jsdir,module_name)
		return ret


	def compress_string(buf):
		import gzip, cStringIO
		zbuf = cStringIO.StringIO()
		zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
		zfile.write(buf)
		zfile.close()
		return zbuf.getvalue()

	compress = 0
	try:
		if string.find(os.environ["HTTP_ACCEPT_ENCODING"], "gzip") != -1:
			compress = 1
	except:
		pass
	
	load_js_module(form.getvalue('module'))
	#load_js_module('wn.modules')
		
	if compress and len(out)>512:
		out_buf = compress_string(str_out)
		print "Content-Encoding: gzip"
		print "Content-Length: %d" % (len(out_buf))
	
	print "Content-Type: text/javascript"
		
	# Headers end
	print 

	if out_buf:
		sys.stdout.write(out_buf)
	elif out:
		import json
		print json.dumps(jsonout)

except Exception, e:
	print "Content-Type: text/javascript"
	print
	print getTraceback()#.replace('\n','<br>')
