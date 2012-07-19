#!/usr/bin/python

from __future__ import unicode_literals
"""
Utilty to review DocType fields:

- Will prompt each field and allow to change properties and fieldnames
- Run from command line of project home
- set fieldname_patch_file in defs.py

# todo 

- update db
- parent field for table fields
"""

import os, sys

curpath = os.path.dirname(__file__)

sys.path.append(os.path.join(curpath, '..', '..'))

import webnotes
import conf
from webnotes.modules.export_module import export_to_files
from termcolor import colored

sys.path.append(conf.modules_path)

def update_field_property(f, property):
	import webnotes

	new = raw_input('New %s: ' % property)
	if new:
		webnotes.conn.begin()
		webnotes.conn.set_value('DocField', f['name'], property, new)
		webnotes.conn.commit()
		export_to_files(record_list=[['DocType', f['parent']]])
		
	return new

def remove_field(f):
	webnotes.conn.begin()
	webnotes.conn.sql("""delete from tabDocField where name=%s""", f['name'])
	webnotes.conn.commit()
	export_to_files(record_list=[['DocType', f['parent']]])

def replace_code(old, new):
	"""find files with fieldname using grep and pass fieldnames to replace code"""
	import subprocess

	# js
	proc = subprocess.Popen(['grep', '-rl', '--include=*.js', old, '.'],
		shell=False, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = proc.communicate()
	for fpath in stdout.split():
		ret = search_replace_with_prompt(fpath, old, new)
		if ret == 'quit':
			break

	# py
	proc = subprocess.Popen(['grep', '-rl', '--include=*.py', old, '.'],
		shell=False, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = proc.communicate()
	for fpath in stdout.split():
		ret = search_replace_with_prompt(fpath, old, new)
		if ret == 'quit':
			break

def update_fieldname_patch_file(fdata):
	"""update patch file with list"""
	with open(conf.fieldname_patch_file, 'a') as patchfile:
		patchfile.write(str(fdata) + '\n')

def search_replace_with_prompt(fpath, txt1, txt2):
	""" Search and replace all txt1 by txt2 in the file with confirmation"""

	from termcolor import colored
	with open(fpath, 'r') as f:
		content = f.readlines()

	tmp = []
	for c in content:
		if c.find(txt1) != -1:
			print '\n', fpath
			print  colored(txt1, 'red').join(c[:-1].split(txt1))
			a = ''
			while a not in ['y', 'n', 'Y', 'N', 's', 'q']:
				a = raw_input('Do you want to Change [y/n/s/q]?')
			if a.lower() == 'y':
				c = c.replace(txt1, txt2)
			if a.lower() == 's':
				return
			if a.lower() == 'q':
				return 'quit'
		tmp.append(c)

	with open(fpath, 'w') as f:
		f.write(''.join(tmp))
	print colored('Updated', 'green')

def review():
	"""review fields"""
	start = 0
	
	flist = webnotes.conn.sql("""select t1.name, t1.parent, t1.fieldtype, t1.label, t1.fieldname, 
		t1.options, t1.description from tabDocField t1, tabDocType t2 where
		t1.fieldtype not in ('Section Break', 'Column Break') and 
		t1.fieldname not in ('address_display', 'contact_display') and
		t1.parent = t2.name and
		t2.module != 'Core' and
		replace(replace(replace(replace(lower(label), ' ', '_'), '-', '_'), ')', ''), '(', '') != fieldname 
		order by parent, label""", as_dict=1)
		
	for f in flist[start:]:
		os.system('clear')
		print f['parent']
		print 'Fieldname: ' + colored(f['fieldname'], 'red')
		print 'Label:' + f['label']
		print 'Description: ' + str(f['description'])
		print 'Type: ' + str(f['fieldtype'])
		print 'Options: ' + str(f['options'])
		print str(start) + '/' + str(len(flist))

		action = ''
		while action != 'n':
			print '-----------------'
			action = raw_input("""[n]ext, [f]ieldname, [l]abel, [d]escription, [r]emove, view [c]ode, [q]uit:""")
			if action=='l':
				old = f['label']
				new = update_field_property(f, 'label')

				# replace code for search criteria
				replace_code(old, new)

			elif action=='d':
				update_field_property(f, 'description')
			elif action=='c':
				print colored('js:', 'green')
				os.system('grep -r --color --include=*.js "%s" ./' % f['fieldname'])
				print colored('py:', 'green')
				os.system('grep -r --color --include=*.py "%s" ./' % f['fieldname'])
			elif action=='f':
				old = f['fieldname']
				new = update_field_property(f, 'fieldname')
				
				if new:
					# rename in table and parentfield
					from webnotes.model import docfield
					docfield.rename(f['parent'], f['fieldname'], new)
				
					# replace code
					replace_code(old, new)
				
					# write in fieldname patch file
					update_fieldname_patch_file([f['parent'], f['fieldname'], new])
				
			elif action=='r':
				remove_field(f)
				action = 'n'
			elif action=='q':
				return
		
		start += 1

def setup_options():
	from optparse import OptionParser
	parser = OptionParser()
	
	parser.add_option("-a", "--all",
						action="store_true", default=False,
						help="Review all fields")

	parser.add_option("-d", "--doctype",
						nargs=1, default=False, metavar='DOCTYPE',
						help="Review fields of a doctype")

	parser.add_option("-f", "--field",
						nargs=2, default=False, metavar='DOCTYPE FIELD',
						help="Review a particular field")
											
	return parser.parse_args()


if __name__=='__main__':
	webnotes.connect()
	options, args = setup_options()
	
	if options.all:
		review()
	
	if options.doctype:
		review(options.doctype)
		
	if options.field:
		review(options.field[0], options.field[1])
	