import random
from string import printable
from time import time
from unittest import TestCase

from frappe.utils.password_strength import test_password_strength


class TestPasswordStrength(TestCase):
	def test_long_password(self):
		password = "".join(random.choice(printable) for _ in range(600))

		start_second = time()
		result = test_password_strength(password)
		end_second = time()

		self.assertLess(end_second - start_second, 10)
		self.assertIn("feedback", result)
