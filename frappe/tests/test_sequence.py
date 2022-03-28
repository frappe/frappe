from frappe.database.sequence import create_sequence, get_next_val, set_next_val

import unittest
import pymysql
import psycopg2


class TestSequence(unittest.TestCase):
	def test_set_next_val(self):
		seq_name = "test_set_next_val_1"
		create_sequence(seq_name, check_not_exists=True)

		next_val = get_next_val(seq_name)
		set_next_val(seq_name, next_val + 1)
		self.assertEqual(next_val + 1, get_next_val(seq_name))

		next_val = get_next_val(seq_name)
		set_next_val(seq_name, next_val + 1, is_val_used=True)
		self.assertEqual(next_val + 2, get_next_val(seq_name))

	def test_create_sequence(self):
		create_sequence("test_create_sequence_1", max_value=2, cycle=True)
		get_next_val("test_create_sequence_1")
		get_next_val("test_create_sequence_1")
		self.assertEqual(1, get_next_val("test_create_sequence_1"))

		create_sequence("test_create_sequence_2", max_value=2)
		get_next_val("test_create_sequence_2")
		get_next_val("test_create_sequence_2")

		try:
			get_next_val("test_create_sequence_2")
		except pymysql.err.OperationalError as e:
			self.assertEqual(e.args[0], 4084)
		except psycopg2.DataError as e:
			self.assertEqual("2200H", e.pgcode)
			print(e)
		else:
			self.fail("NEXTVAL didn't raise any error upon sequence's end")

		create_sequence("test_create_sequence_3", min_value=10, max_value=20, increment_by=5)
		self.assertEqual(10, get_next_val("test_create_sequence_3"))
		self.assertEqual(15, get_next_val("test_create_sequence_3"))
		self.assertEqual(20, get_next_val("test_create_sequence_3"))
