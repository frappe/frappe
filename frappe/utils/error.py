# -*- coding: utf-8 -*-
# Copyright (c) 2015, Maxwell Morais and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import os
import sys
import inspect
import traceback
import linecache
import pydoc
import cgitb
import types
import uuid
import datetime
import json

import frappe

def error_collector(exception):
	ticket_id = '{ip:s}.{timestamp:s}.{uuid:s}'.format(
		ip=frappe.local.request_ip or '127.0.0.1',
		timestamp=str(datetime.datetime.now()),
		uuid=str(uuid.uuid4())
	)

	store_folder = frappe.get_site_path('tickets')
	if not os.path.exists(store_folder):
		os.mkdir(store_folder)

	snap = snapshot(exception)

	with file(os.path.join(store_folder, ticket_id)+'.json', 'wb') as ticket:
		json.dump(snap, ticket)

	print 'New ticket collected with id `{}`'.format(ticket_id)

def snapshot(exception):
	"""
	Return a dict describing a given traceback (based on cgitb.text)
	"""

	etype, evalue, etb = sys.exc_info()
	if isinstance(etype, types.ClassType):
		etype = etype.__name__

	# creates a snapshot dict with some basic information

	s = {
		'pyver': 'Python {version:s}: {executable:s} (prefix: {prefix:s})'.format(
			version = sys.version.split()[0],
			executable = sys.executable,
			prefix = sys.prefix
		),
		'timestamp': str(datetime.datetime.now()),
		'traceback': traceback.format_exc(),
		'frames': [],
		'etype': str(etype),
		'evalue': str(evalue),
		'exception': {},
		'locals': {}
	}

	# start to process frames
	records = inspect.getinnerframes(etb, 5)
	for frame, file, lnum, func, lines, index in records:
		file = file and os.path.abspath(file) or '?'
		args, varargs, varkw, locals = inspect.getargvalues(frame)
		call = ''

		if func != '?':
			call = inspect.formatargvalues(args, varargs, varkw, locals, formatvalue=lambda value: '={}'.format(pydoc.text.repr(value)))

		# basic frame information
		f = {'file': file, 'func': func, 'call': call, 'lines': {}, 'lnum': lnum}

		def reader(lnum=[lnum]):
			try:
				return linecache.getline(file, lnum[0])
			finally:
				lnum[0] += 1

		vars = cgitb.scanvars(reader, frame, locals)

		# if it is a view, replace with generated code
		if file.endswith('html'):
			lmin = lnum > context and (lnum - context) or 0
			lmax = lnum + context
			lines = code.split("\n")[lmin:lmax]
			index = min(context, lnum) - 1

		if index is not None:
			i = lnum - index
			for line in lines:
				f['lines'][i] = line.rstrip()
				i += 1

		# dump local variable (referenced in current line only)
		f['dump'] = {}
		for name, where, value in vars:
			if name in f['dump']:
				continue
			if value is not cgitb.__UNDEF__:
				if where == 'global':
					name = 'global {name:s}'.format(name=name)
				elif where != 'local':
					name = where + ' ' + name.split('.')[-1]
				f['dump'][name] = pydoc.text.repr(value)
			else:
				f['dump'][name] = 'undefined'

		s['frames'].append(f)

	# add exception type, value and attributes
	if isinstance(evalue, BaseException):
		for name in dir(evalue):
			# prevent py26 DeprecationWarning
			if (name != 'messages' or sys.version_info < (2.6)) and not name.startswith('__'):
				value = pydoc.text.repr(getattr(evalue, name))
				s['exception'][name] = value

	# add all local values (of last frame) to the snapshot
	for name, value in locals.items():
		s['locals'][name] = pydoc.text.repr(value)

	return s
