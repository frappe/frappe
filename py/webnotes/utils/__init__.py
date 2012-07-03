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

# util __init__.py

import webnotes

user_time_zone = None
month_name = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
month_name_full = ['','January','February','March','April','May','June','July','August','September','October','November','December']
no_value_fields = ['Section Break', 'Column Break', 'HTML', 'Table', 'FlexTable', 'Button', 'Image', 'Graph']
default_fields = ['doctype','name','owner','creation','modified','modified_by','parent','parentfield','parenttype','idx','docstatus']

def getCSVelement(v):
	"""
		 Returns the CSV value of `v`, For example: 
		 
		 * apple becomes "apple"
		 * hi"there becomes "hi""there"
	"""
	v = cstr(v)
	if not v: return ''
	if (',' in v) or ('\n' in v) or ('"' in v):
		if '"' in v: v = v.replace('"', '""')
		return '"'+v+'"'
	else: return v or ''

def get_fullname(profile):
	"""get the full name (first name + last name) of the user from Profile"""
	p = webnotes.conn.sql("""select first_name, last_name from `tabProfile`
		where name=%s""", profile, as_dict=1)
	if p:
		p = p[0]
		full_name = (p['first_name'] and (p['first_name'] + ' ') or '') + (p['last_name'] or '')
		return full_name or profile
	else:
		return profile
		
def extract_email_id(s):
	"""
		Extract email id from email header format
	"""
	if '<' in s:
		s = s.split('<')[1].split('>')[0]
	if s: 
		s = s.strip().lower()
	return s
	
def validate_email_add(email_str):
	"""
		Validates the email string
	"""
	s = extract_email_id(email_str)
	import re
	#return re.match("^[a-zA-Z0-9._%-]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", email_str)
	return re.match("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", s)

def sendmail(recipients, sender='', msg='', subject='[No Subject]', parts=[], cc=[], attach=[]):
	"""
	Send an email. For more details see :func:`email_lib.sendmail`
	"""
	import webnotes.utils.email_lib
	return email_lib.sendmail(recipients, sender, msg, subject, parts, cc, attach)
	
def generate_hash():
	"""
		 Generates random hash for session id
	"""
	import hashlib, time
	return hashlib.sha224(str(time.time())).hexdigest()

def random_string(length):
	"""generate a random string"""
	import string
	from random import choice
	return ''.join([choice(string.letters + string.digits) for i in range(length)])

def db_exists(dt, dn):
	return webnotes.conn.sql('select name from `tab%s` where name="%s"' % (dt, dn))

def load_json(arg):
	# already a dictionary?
	if not isinstance(arg, basestring):
		return arg
	
	import json
	return json.loads(arg, encoding='utf-8')
	
# Get Traceback
# ==============================================================================

def getTraceback():
	"""
		 Returns the traceback of the Exception
	"""
	import sys, traceback, string
	type, value, tb = sys.exc_info()
	
	body = "Traceback (innermost last):\n"
	list = traceback.format_tb(tb, None) + traceback.format_exception_only(type, value)
	body = body + "%-20s %s" % (string.join(list[:-1], ""), list[-1])
	
	if webnotes.logger:
		webnotes.logger.error('Db:'+(webnotes.conn and webnotes.conn.cur_db_name or '') + ' - ' + body)
	
	return body

# Log
# ==============================================================================

def log(event, details):
	webnotes.logger.info(details)

# Date and Time
# ==============================================================================


def getdate(string_date):
	"""
		 Coverts string date (yyyy-mm-dd) to datetime.date object
	"""
	import datetime

	if type(string_date)==unicode:
		string_date = str(string_date)
	
	if type(string_date) in (datetime.datetime, datetime.date): 
		return string_date
	
	if ' ' in string_date:
		string_date = string_date.split(' ')[0]
	t = string_date.split('-')
	if len(t)==3:
		return datetime.date(cint(t[0]), cint(t[1]), cint(t[2]))
	else:
		return ''

def add_days(date, days, format='string'):
	"""
		 Adds `days` to the given `string_date`
	"""
	import datetime
	if not date:
		date = now_datetime()

	if type(date) not in (datetime.datetime, datetime.date): 
		date = getdate(date)

	dt =  date + datetime.timedelta(days)
	if format=='string':
		return dt.strftime('%Y-%m-%d')
	else:
		return dt

def add_months(string_date, months):
	import datetime
	return webnotes.conn.sql("select DATE_ADD('%s',INTERVAL '%s' MONTH)" % (getdate(string_date),months))[0][0]

def add_years(string_date, years):
	import datetime
	return webnotes.conn.sql("select DATE_ADD('%s',INTERVAL '%s' YEAR)" % (getdate(string_date),years))[0][0]

def date_diff(string_ed_date, string_st_date=None):
	import datetime
	return webnotes.conn.sql("SELECT DATEDIFF('%s','%s')" %(getdate(string_ed_date), getdate(string_st_date)))[0][0]

def now_datetime():
	global user_time_zone
	from datetime import datetime
	from pytz import timezone
	
	# get localtime
	if not user_time_zone:
		user_time_zone = webnotes.conn.get_value('Control Panel', None, 'time_zone') \
			or 'Asia/Calcutta'

	# convert to UTC
	utcnow = timezone('UTC').localize(datetime.utcnow())

	# convert to user time zone
	return utcnow.astimezone(timezone(user_time_zone))

def now():
	"""return current datetime as yyyy-mm-dd hh:mm:ss"""
	return now_datetime().strftime('%Y-%m-%d %H:%M:%S')
	
def nowdate():
	"""return current date as yyyy-mm-dd"""
	return now_datetime().strftime('%Y-%m-%d')

def nowtime():
	"""return current time in hh:mm"""
	return now_datetime().strftime('%H:%M')

def get_first_day(dt, d_years=0, d_months=0):
	"""
	 Returns the first day of the month for the date specified by date object
	 Also adds `d_years` and `d_months` if specified
	"""
	import datetime
	# d_years, d_months are "deltas" to apply to dt
	y, m = dt.year + d_years, dt.month + d_months
	a, m = divmod(m-1, 12)
	return datetime.date(y+a, m+1, 1)

def get_last_day(dt):
	"""
	 Returns last day of the month using:
	 `get_first_day(dt, 0, 1) + datetime.timedelta(-1)`
	"""
	import datetime
	return get_first_day(dt, 0, 1) + datetime.timedelta(-1)

user_format = None
"""
	 User format specified in :term:`Control Panel`
	 
	 Examples:
	 
	 * dd-mm-yyyy
	 * mm-dd-yyyy
	 * dd/mm/yyyy
"""

def formatdate(string_date):
	"""
	 	Convers the given string date to :data:`user_format`
	"""
	global user_format
	if not user_format:
		user_format = webnotes.conn.get_value('Control Panel', None, 'date_format')
	d = string_date.split('-');
	out = user_format
	return out.replace('dd', ('%.2i' % cint(d[2]))).replace('mm', ('%.2i' % cint(d[1]))).replace('yyyy', d[0])
	
def dict_to_str(args, sep='&'):
	"""
	Converts a dictionary to URL
	"""
	import urllib
	t = []
	for k in args.keys():
		t.append(str(k)+'='+urllib.quote(str(args[k] or '')))
	return sep.join(t)

def timestamps_equal(t1, t2):
	"""Returns true if same the two string timestamps are same"""
	scrub = lambda x: x.replace(':', ' ').replace('-',' ').split()

	t1, t2 = scrub(t1), scrub(t2)
	
	if len(t1) != len(t2):
		return
	
	for i in range(len(t1)):
		if t1[i]!=t2[i]:
			return
	return 1

def global_date_format(date):
	"""returns date as 1 January 2012"""
	import datetime

	if isinstance(date, basestring):
		date = getdate(date)
	
	return date.strftime('%d') + ' ' + month_name_full[int(date.strftime('%m'))] \
		+ ' ' + date.strftime('%Y')
	
	
	

# Datatype
# ==============================================================================

def isNull(v):
	"""
	Returns true if v='' or v is `None`
	"""
	return (v=='' or v==None)
	
def has_common(l1, l2):
	"""
	Returns true if there are common elements in lists l1 and l2
	"""
	for l in l1:
		if l in l2: 
			return 1
	return 0
	
def flt(s):
	"""
	Convert to float (ignore commas)
	"""
	if isinstance(s, basestring): # if string
		s = s.replace(',','')
	try: tmp = float(s)
	except: tmp = 0
	return tmp

def cint(s):
	"""
	Convert to integer
	"""
	try: tmp = int(float(s))
	except: tmp = 0
	return tmp

def cstr(s):
	"""	
	Convert to string
	"""
	if isinstance(s, basestring):
		return s
	elif s==None: 
		return ''
	else:
		return str(s)
		
def str_esc_quote(s):
	"""
	Escape quotes
	"""
	if s==None:return ''
	return s.replace("'","\'")

def replace_newlines(s):
	"""
	Replace newlines by '<br>'
	"""
	if s==None:return ''
	return s.replace("\n","<br>")


# ==============================================================================

def parse_val(v):
	"""
	Converts to simple datatypes from SQL query results
	"""
	import datetime
	
	if type(v)==datetime.date:
		v = str(v)
	elif type(v)==datetime.timedelta:
		v = ':'.join(str(v).split(':')[:2])
	elif type(v)==datetime.datetime:
		v = str(v)
	elif type(v)==long: v=int(v)

	return v
	
# ==============================================================================

def fmt_money(amount, fmt = '%.2f'):
	"""
	Convert to string with commas for thousands, millions etc
	"""
	curr = webnotes.conn.get_value('Control Panel', None, 'currency_format') or 'Millions'

	val = 2
	if curr == 'Millions': val = 3

	if cstr(amount).find('.') == -1:	temp = '00'
	else: temp = cstr(amount).split('.')[1]

	l = []
	minus = ''
	if flt(amount) < 0: minus = '-'

	amount = ''.join(cstr(amount).split(','))
	amount = cstr(abs(flt(amount))).split('.')[0]
	
	# main logic	
	if len(cstr(amount)) > 3:
		nn = amount[len(amount)-3:]
		l.append(nn)
		amount = amount[0:len(amount)-3]
		while len(cstr(amount)) > val:
			nn = amount[len(amount)-val:]
			l.insert(0,nn)
			amount = amount[0:len(amount)-val]
	
	if len(amount) > 0:	l.insert(0,amount)

	amount = ','.join(l)+'.'+temp
	amount = minus + amount
	return amount

#
# convet currency to words
#
def money_in_words(number, main_currency = None, fraction_currency=None):
	"""
	Returns string in words with currency and fraction currency. 
	"""
	
	d = get_defaults()
	if not main_currency:
		main_currency = d.get('currency', 'INR')
	if not fraction_currency:
		fraction_currency = d.get('fraction_currency', 'paise')

	n = "%.2f" % flt(number)
	main, fraction = n.split('.')
	if len(fraction)==1: fraction += '0'
	
	out = main_currency + ' ' + in_words(main).title()
	if cint(fraction):
		out = out + ' and ' + in_words(fraction).title() + ' ' + fraction_currency

	return out + ' only.'

#
# convert number to words
#
def in_words(integer):
	"""
	Returns string in words for the given integer.
	"""

	in_million = webnotes.conn.get_default('currency_format')=='Millions' and 1 or 0

	n=int(integer)
	known = {0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
		11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen', 15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen',
		19: 'nineteen', 20: 'twenty', 30: 'thirty', 40: 'forty', 50: 'fifty', 60: 'sixty', 70: 'seventy', 80: 'eighty', 90: 'ninety'}
	
	def psn(n, known, xpsn):
		import sys; 
		if n in known: return known[n]
		bestguess, remainder = str(n), 0

		if n<=20:
			print >>sys.stderr, n, "How did this happen?"
			assert 0
		elif n < 100:
			bestguess= xpsn((n//10)*10, known, xpsn) + '-' + xpsn(n%10, known, xpsn)
			return bestguess
		elif n < 1000:
			bestguess= xpsn(n//100, known, xpsn) + ' ' + 'hundred'
			remainder = n%100
		else:
			if in_million:
				if n < 1000000:
					bestguess= xpsn(n//1000, known, xpsn) + ' ' + 'thousand'
					remainder = n%1000
				elif n < 1000000000:
					bestguess= xpsn(n//1000000, known, xpsn) + ' ' + 'million'
					remainder = n%1000000
				else:
					bestguess= xpsn(n//1000000000, known, xpsn) + ' ' + 'billion'
					remainder = n%1000000000				
			else:
				if n < 100000:
					bestguess= xpsn(n//1000, known, xpsn) + ' ' + 'thousand'
					remainder = n%1000
				elif n < 10000000:
					bestguess= xpsn(n//100000, known, xpsn) + ' ' + 'lakh'
					remainder = n%100000
				else:
					bestguess= xpsn(n//10000000, known, xpsn) + ' ' + 'crore'
					remainder = n%10000000
		if remainder:
			if remainder >= 100:
				comma = ','
			else:
				comma = ''
			return bestguess + comma + ' ' + xpsn(remainder, known, xpsn)
		else:
			return bestguess

	return psn(n, known, psn)
	

# Get Defaults
# ==============================================================================

def get_defaults(key=None):
	"""
	Get dictionary of default values from the :term:`Control Panel`, or a value if key is passed
	"""
	return webnotes.conn.get_defaults(key)

def set_default(key, val):
	"""
	Set / add a default value to :term:`Control Panel`
	"""
	return webnotes.conn.set_default(key, val)

#
# Clear recycle bin
#
def clear_recycle_bin():
	sql = webnotes.conn.sql
	
	tl = sql('show tables')
	total_deleted = 0
	for t in tl:
		fl = [i[0] for i in sql('desc `%s`' % t[0])]
		
		if 'name' in fl:
			total_deleted += sql("select count(*) from `%s` where name like '__overwritten:%%'" % t[0])[0][0]
			sql("delete from `%s` where name like '__overwritten:%%'" % t[0])

		if 'parent' in fl:	
			total_deleted += sql("select count(*) from `%s` where parent like '__oldparent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like '__oldparent:%%'" % t[0])
	
			total_deleted += sql("select count(*) from `%s` where parent like 'oldparent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like 'oldparent:%%'" % t[0])

			total_deleted += sql("select count(*) from `%s` where parent like 'old_parent:%%'" % t[0])[0][0]
			sql("delete from `%s` where parent like 'old_parent:%%'" % t[0])

	return "%s records deleted" % str(int(total_deleted))

# Dictionary utils
# ==============================================================================

def remove_blanks(d):
	"""
		Returns d with empty ('' or None) values stripped
	"""
	empty_keys = []
	for key in d:
		if d[key]=='' or d[key]==None:
			# del d[key] raises runtime exception, using a workaround
			empty_keys.append(key)
	for key in empty_keys:
		del d[key]
		
	return d
		
def pprint_dict(d, level=1, no_blanks=True):
	"""
		Pretty print a dictionary with indents
	"""
	if no_blanks:
		remove_blanks(d)
		
	# make indent
	indent, ret = '', ''
	for i in range(0,level): indent += '\t'
	
	# add lines
	comment, lines = '', []
	kl = d.keys()
	kl.sort()
		
	# make lines
	for key in kl:
		if key != '##comment':
			tmp = {key: d[key]}
			lines.append(indent + str(tmp)[1:-1] )
	
	# add comment string
	if '##comment' in kl:
		ret = ('\n' + indent) + '# ' + d['##comment'] + '\n'

	# open
	ret += indent + '{\n'
	
	# lines
	ret += indent + ',\n\t'.join(lines)
	
	# close
	ret += '\n' + indent + '}'
	
	return ret
				
def get_common(d1,d2):
	"""
		returns (list of keys) the common part of two dicts
	"""
	return [p for p in d1 if p in d2 and d1[p]==d2[p]]

def get_common_dict(d1, d2):
	"""
		return common dictionary of d1 and d2
	"""
	ret = {}
	for key in d1:
		if key in d2 and d2[key]==d1[key]:
			ret[key] = d1[key]
	return ret

def get_diff_dict(d1, d2):
	"""
		return common dictionary of d1 and d2
	"""
	diff_keys = set(d2.keys()).difference(set(d1.keys()))
	
	ret = {}
	for d in diff_keys: ret[d] = d2[d]
	return ret


def get_file_timestamp(fn):
	"""
		Returns timestamp of the given file
	"""
	import os
	from webnotes.utils import cint
	
	try:
		return str(cint(os.stat(fn).st_mtime))
	except OSError, e:
		if e.args[0]!=2:
			raise e
		else:
			return None

# to be deprecated
def make_esc(esc_chars):
	"""
		Function generator for Escaping special characters
	"""
	return lambda s: ''.join(['\\' + c if c in esc_chars else c for c in s])

# esc / unescape characters -- used for command line
def esc(s, esc_chars):
	"""
		Escape special characters
	"""
	for c in esc_chars:
		esc_str = '\\' + c
		s = s.replace(c, esc_str)
	return s

def unesc(s, esc_chars):
	"""
		UnEscape special characters
	"""
	for c in esc_chars:
		esc_str = '\\' + c
		s = s.replace(esc_str, c)
	return s

def get_doctype_label(dt=None):
	"""
		Gets label of a doctype
	"""
	if dt:
		res = webnotes.conn.sql("""\
			SELECT name, dt_label FROM `tabDocType Label`
			WHERE name=%s""", dt)
		return res and res[0][0] or dt
	else:
		res = webnotes.conn.sql("SELECT name, dt_label FROM `tabDocType Label`")
		dt_label_dict = {}
		for r in res:
			dt_label_dict[r[0]] = r[1]

		return dt_label_dict


def get_label_doctype(label):
	"""
		Gets doctype from its label
	"""
	res = webnotes.conn.sql("""\
		SELECT name FROM `tabDocType Label`
		WHERE dt_label=%s""", label)

	return res and res[0][0] or label


def get_system_managers_list():
	"""Returns a list of system managers' email addresses"""
	system_managers_list = webnotes.conn.sql("""\
		SELECT DISTINCT p.name
		FROM tabUserRole ur, tabProfile p
		WHERE
			ur.parent = p.name AND
			ur.role='System Manager' AND
			p.docstatus<2 AND
			p.enabled=1 AND
			p.name not in ('Administrator', 'Guest')""", as_list=1)

	return [sysman[0] for sysman in system_managers_list]
