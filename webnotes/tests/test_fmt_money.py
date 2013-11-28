# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
from webnotes import _
from webnotes.utils import flt, cstr

def fmt_money(amount, precision=None):
	"""
	Convert to string with commas for thousands, millions etc
	"""
	
	number_format = webnotes.conn.get_default("number_format") or "#,###.##"
	decimal_str, comma_str, precision = get_number_format_info(number_format)
	
	
	amount = '%.*f' % (precision, flt(amount))
	if amount.find('.') == -1:
		decimals = ''
	else: 
		decimals = amount.split('.')[1]

	parts = []
	minus = ''
	if flt(amount) < 0: 
		minus = '-'

	amount = cstr(abs(flt(amount))).split('.')[0]

	if len(amount) > 3:
		parts.append(amount[-3:])
		amount = amount[:-3]

		val = number_format=="#,##,###.##" and 2 or 3

		while len(amount) > val:
			parts.append(amount[-val:])
			amount = amount[:-val]

	parts.append(amount)

	parts.reverse()

	amount = comma_str.join(parts) + (precision and (decimal_str + decimals) or "")
	amount = minus + amount

	return amount
	
def get_number_format_info(format):
	if format=="#.###":
		return "", ".", 0
	elif format=="#,###":
		return "", ",", 0
	elif format=="#,###.##" or format=="#,##,###.##":
		return ".", ",", 2
	elif format=="#.###,##":
		return ",", ".", 2
	elif format=="# ###.##":
		return ".", " ", 2
	else:
		return ".", ",", 2

import unittest

class TestFmtMoney(unittest.TestCase):
	def test_standard(self):
		webnotes.conn.set_default("number_format", "#,###.##")
		self.assertEquals(fmt_money(100), "100.00")
		self.assertEquals(fmt_money(1000), "1,000.00")
		self.assertEquals(fmt_money(10000), "10,000.00")
		self.assertEquals(fmt_money(100000), "100,000.00")
		self.assertEquals(fmt_money(1000000), "1,000,000.00")
		self.assertEquals(fmt_money(10000000), "10,000,000.00")
		self.assertEquals(fmt_money(100000000), "100,000,000.00")
		self.assertEquals(fmt_money(1000000000), "1,000,000,000.00")

	def test_negative(self):
		webnotes.conn.set_default("number_format", "#,###.##")
		self.assertEquals(fmt_money(-100), "-100.00")
		self.assertEquals(fmt_money(-1000), "-1,000.00")
		self.assertEquals(fmt_money(-10000), "-10,000.00")
		self.assertEquals(fmt_money(-100000), "-100,000.00")
		self.assertEquals(fmt_money(-1000000), "-1,000,000.00")
		self.assertEquals(fmt_money(-10000000), "-10,000,000.00")
		self.assertEquals(fmt_money(-100000000), "-100,000,000.00")
		self.assertEquals(fmt_money(-1000000000), "-1,000,000,000.00")

	def test_decimal(self):
		webnotes.conn.set_default("number_format", "#.###,##")
		self.assertEquals(fmt_money(-100), "-100,00")
		self.assertEquals(fmt_money(-1000), "-1.000,00")
		self.assertEquals(fmt_money(-10000), "-10.000,00")
		self.assertEquals(fmt_money(-100000), "-100.000,00")
		self.assertEquals(fmt_money(-1000000), "-1.000.000,00")
		self.assertEquals(fmt_money(-10000000), "-10.000.000,00")
		self.assertEquals(fmt_money(-100000000), "-100.000.000,00")
		self.assertEquals(fmt_money(-1000000000), "-1.000.000.000,00")


	def test_lacs(self):
		webnotes.conn.set_default("number_format", "#,##,###.##")
		self.assertEquals(fmt_money(100), "100.00")
		self.assertEquals(fmt_money(1000), "1,000.00")
		self.assertEquals(fmt_money(10000), "10,000.00")
		self.assertEquals(fmt_money(100000), "1,00,000.00")
		self.assertEquals(fmt_money(1000000), "10,00,000.00")
		self.assertEquals(fmt_money(10000000), "1,00,00,000.00")
		self.assertEquals(fmt_money(100000000), "10,00,00,000.00")
		self.assertEquals(fmt_money(1000000000), "1,00,00,00,000.00")

	def test_no_precision(self):
		webnotes.conn.set_default("number_format", "#,###")
		self.assertEquals(fmt_money(0.3), "0")
		self.assertEquals(fmt_money(100.3), "100")
		self.assertEquals(fmt_money(1000.3), "1,000")
		self.assertEquals(fmt_money(10000.3), "10,000")
		self.assertEquals(fmt_money(-0.3), "0")
		self.assertEquals(fmt_money(-100.3), "-100")
		self.assertEquals(fmt_money(-1000.3), "-1,000")

if __name__=="__main__":
	webnotes.connect()
	unittest.main()